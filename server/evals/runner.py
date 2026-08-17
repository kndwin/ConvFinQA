import argparse
import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
from ag_ui.core import RunAgentInput, UserMessage
from src.module.agent_execution.agent_approach.baseline.prompts.registry import (
    resolve as _resolve_baseline_prompt,
)
from src.module.agent_execution.agent_approach.baseline_tool.prompts.registry import (
    resolve as _resolve_tool_prompt,
)
from src.module.agent_execution.agent_approach.program_of_thought.prompts.registry import (
    resolve as _resolve_pot_prompt,
)
from src.module.agent_execution.agent_approach.shared.context.document_conversation import VERSION
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_runner_schema import PromptVersion

from evals.golden import build_golden, golden_shape
from evals.scoring import score_dict, score_numeric

DEFAULT_URL = "http://127.0.0.1:8000"
TARGETS = {
    "baseline:v1": "baseline",
    "baseline-tool:v1": "baseline-tool",
    "program-of-thought:v1": "program-of-thought",
}
TARGET_RESOLVERS = {
    "baseline:v1": _resolve_baseline_prompt,
    "baseline-tool:v1": _resolve_tool_prompt,
    "program-of-thought:v1": _resolve_pot_prompt,
}


@dataclass(frozen=True)
class EvaluationTarget:
    id: str
    agent_approach: AgentApproach
    prompt: PromptVersion
    context_version: str
    context_hash: str

    @property
    def prompt_version(self) -> str:
        return self.prompt.id


def _target(target_id: str) -> EvaluationTarget:
    approach = AgentApproach(TARGETS[target_id])
    prompt = TARGET_RESOLVERS[target_id](target_id)
    return EvaluationTarget(target_id, approach, prompt, VERSION.id, VERSION.definition_hash)


def parse_targets(values: list[str]) -> list[EvaluationTarget]:
    result: list[EvaluationTarget] = []
    for target in values:
        if target not in TARGETS:
            raise ValueError(f"Unsupported evaluation target: {target}")
        result.append(_target(target))
    return result


def _target_fields(target: EvaluationTarget, model: str) -> dict[str, str]:
    return {
        "target": target.id,
        "agent_approach": str(target.agent_approach),
        "prompt_version": target.prompt_version,
        "prompt_hash": target.prompt.content_hash,
        "context_version": target.context_version,
        "context_hash": target.context_hash,
        "model": model,
    }


async def _get(client: httpx.AsyncClient, url: str, dataset_id: int) -> dict[str, Any]:
    response = await client.get(f"{url}/dataset-conversations/{dataset_id}")
    response.raise_for_status()
    return response.json()


def _event_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    if str(data.get("type", "")).upper() != "TEXT_MESSAGE_CONTENT":
        return ""
    for key in ("delta", "content", "text"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return ""


def _event_error(data: Any) -> str | None:
    if isinstance(data, dict) and str(data.get("type", "")).upper() == "RUN_ERROR":
        return str(data.get("message") or data.get("error") or data)
    return None


async def _run_turn(
    client: httpx.AsyncClient,
    url: str,
    dataset_id: int,
    session_id: int,
    messages: list[dict[str, Any]],
    question: str,
) -> tuple[str, float]:
    messages.append(UserMessage(id=str(uuid.uuid4()), content=question).model_dump(mode="json"))
    payload = RunAgentInput(
        thread_id=str(session_id),
        run_id=str(uuid.uuid4()),
        state={},
        messages=messages,
        tools=[],
        context=[],
        forwarded_props={},
    )
    started = time.perf_counter()
    parts: list[str] = []
    async with client.stream(
        "POST",
        f"{url}/dataset-conversations/{dataset_id}/chat-sessions/{session_id}/runs",
        json=payload.model_dump(mode="json"),
        headers={"Accept": "text/event-stream"},
    ) as response:
        response.raise_for_status()
        event_data: list[str] = []

        def process_event() -> None:
            if not event_data:
                return
            try:
                event = json.loads("".join(event_data))
            except json.JSONDecodeError:
                event_data.clear()
                return
            error = _event_error(event)
            if error:
                raise RuntimeError(f"Evaluation run failed: {error}")
            text = _event_text(event)
            if text:
                parts.append(text)
            event_data.clear()

        async for line in response.aiter_lines():
            if line.startswith("data:"):
                event_data.append(line[5:].strip())
            elif not line and event_data:
                process_event()
        process_event()
    answer = "".join(parts)
    if not answer.strip():
        raise RuntimeError("Evaluation run finished without an assistant response")
    messages.append({"id": str(uuid.uuid4()), "role": "assistant", "content": answer})
    return answer, time.perf_counter() - started


async def run(config: argparse.Namespace) -> dict[str, Any]:
    targets = parse_targets(config.targets)
    if getattr(config, "mode", "direct") == "direct":
        return await _run_direct(config, targets)
    async with httpx.AsyncClient(base_url=config.base_url, timeout=None) as client:
        datasets = [
            await _get(client, config.base_url, dataset_id) for dataset_id in config.dataset_ids
        ]
        goldens = [build_golden(dataset) for dataset in datasets]
        if config.dry_run:
            return {
                "config": vars(config),
                "resolved_targets": [_target_fields(target, config.model) for target in targets],
                "goldens": [golden_shape(golden) for golden in goldens],
            }
        turns: list[dict[str, Any]] = []
        for dataset, golden in zip(datasets, goldens, strict=True):
            metadata = cast(dict[str, Any], golden.additional_metadata)
            questions = cast(list[str], metadata["questions"])
            answers = cast(list[str | None], metadata["answers"])
            for target in targets:
                response = await client.post(
                    f"/dataset-conversations/{dataset['id']}/chat-sessions",
                    json={"agent_approach": target.agent_approach, "model": config.model},
                )
                response.raise_for_status()
                session = response.json()
                if (
                    session.get("agent_approach") != target.agent_approach
                    or session.get("prompt_version") != target.prompt_version
                    or session.get("context_version") != target.context_version
                ):
                    raise RuntimeError(f"Session configuration does not match target {target.id}")
                session_id = session["id"]
                messages: list[dict[str, Any]] = []
                run_error: BaseException | None = None
                try:
                    for index, question in enumerate(questions):
                        actual, latency = await _run_turn(
                            client, config.base_url, dataset["id"], session_id, messages, question
                        )
                        turns.append(
                            {
                                **_target_fields(target, config.model),
                                "dataset_id": dataset["id"],
                                "turn": index + 1,
                                "question": question,
                                "expected": answers[index],
                                "actual": actual,
                                "latency_seconds": latency,
                                "score": score_dict(
                                    score_numeric(str(answers[index] or ""), actual)
                                ),
                            }
                        )
                except BaseException as error:
                    run_error = error
                    raise
                finally:
                    if not config.keep_sessions:
                        try:
                            cleanup = await client.delete(
                                f"/dataset-conversations/{dataset['id']}/chat-sessions/{session_id}"
                            )
                            if run_error is None:
                                cleanup.raise_for_status()
                        except Exception:
                            if run_error is None:
                                raise
        aggregates: dict[str, dict[str, Any]] = {}
        for target in targets:
            items = [item for item in turns if item["target"] == target.id]
            conversation_ids = {item["dataset_id"] for item in items}
            correct_by_conversation = [
                all(
                    item["score"]["exact_match"]
                    for item in items
                    if item["dataset_id"] == dataset_id
                )
                for dataset_id in conversation_ids
            ]
            aggregates[target.id] = {
                **_target_fields(target, config.model),
                "turn_execution_accuracy": (
                    sum(item["score"]["exact_match"] for item in items) / len(items) if items else 0
                ),
                "fully_correct_conversations": sum(correct_by_conversation),
                "conversation_count": len(conversation_ids),
                "mean_latency_seconds": (
                    sum(item["latency_seconds"] for item in items) / len(items) if items else 0
                ),
            }
    return {"config": vars(config), "aggregates": aggregates, "turns": turns}


async def _run_direct(
    config: argparse.Namespace, targets: list[EvaluationTarget]
) -> dict[str, Any]:
    """Run the same runner as HTTP without a web server or temporary sessions."""
    from ag_ui.core import RunErrorEvent, TextMessageContentEvent
    from src.module.agent_execution.agent_execution_constants import OpenAIModel
    from src.module.agent_execution.agent_execution_service import AgentExecutionService
    from src.module.agent_execution.agent_execution_service_schema import (
        AgentExecutionServiceRunParams,
    )
    from src.module.agent_execution.repositories.in_memory import InMemoryAgentExecutionRepository
    from src.module.dataset_conversations.dataset_conversations_repository import (
        DatasetConversationRepository,
    )
    from src.module.dataset_conversations.dataset_conversations_repository_schema import (
        DatasetConversationRepositoryGetParams,
    )
    from src.platform.database.database import session_factory
    from src.platform.observability import NOOP_OBSERVABILITY, Observability
    from src.platform.openai import openai_client

    async with session_factory() as session:
        repository = DatasetConversationRepository(session, cast(Observability, NOOP_OBSERVABILITY))
        datasets = []
        for dataset_id in config.dataset_ids:
            dataset = await repository.get(
                DatasetConversationRepositoryGetParams(dataset_conversation_id=dataset_id)
            )
            if dataset is None:
                raise RuntimeError(f"Dataset conversation not found: {dataset_id}")
            datasets.append(
                {
                    "id": dataset.id,
                    "doc_json": dataset.doc_json or "",
                    "dialogue_json": dataset.dialogue_json,
                }
            )
        goldens = [build_golden(dataset) for dataset in datasets]
        if config.dry_run:
            return {
                "config": vars(config),
                "resolved_targets": [_target_fields(target, config.model) for target in targets],
                "goldens": [golden_shape(golden) for golden in goldens],
            }
        async with openai_client() as client:
            service = AgentExecutionService(client)
            turns: list[dict[str, Any]] = []
            for dataset, golden in zip(datasets, goldens, strict=True):
                metadata = cast(dict[str, Any], golden.additional_metadata)
                repository_by_target = {
                    target.id: InMemoryAgentExecutionRepository() for target in targets
                }
                for target in targets:
                    repository = repository_by_target[target.id]
                    prompt_override = target.prompt
                    for index, question in enumerate(cast(list[str], metadata["questions"])):
                        started = time.perf_counter()
                        input_data = RunAgentInput(
                            thread_id=str(dataset["id"]),
                            run_id=str(uuid.uuid4()),
                            state={},
                            messages=[UserMessage(id=str(uuid.uuid4()), content=question)],
                            tools=[],
                            context=[],
                            forwarded_props={},
                        )
                        parts: list[str] = []
                        params = AgentExecutionServiceRunParams(
                            approach=target.agent_approach,
                            prompt_version=None,
                            context_version="document-conversation:v1",
                            document=str(dataset["doc_json"]),
                            prompt_override=prompt_override,
                            model=OpenAIModel(config.model),
                            input_data=input_data,
                            trace_metadata={
                                "conversation_id": str(dataset["id"]),
                                "agent_approach": str(target.agent_approach),
                                "model": config.model,
                            },
                        )
                        async for event in service.run(params, repository):
                            if isinstance(event, TextMessageContentEvent):
                                parts.append(event.delta)
                            if isinstance(event, RunErrorEvent):
                                raise RuntimeError(event.message)
                        actual = "".join(parts)
                        expected = cast(list[str | None], metadata["answers"])[index]
                        turns.append(
                            {
                                "dataset_id": dataset["id"],
                                **_target_fields(target, config.model),
                                "turn": index + 1,
                                "question": question,
                                "expected": expected,
                                "actual": actual,
                                "latency_seconds": time.perf_counter() - started,
                                "score": score_dict(score_numeric(str(expected or ""), actual)),
                            }
                        )
            aggregates = {}
            for target in targets:
                items = [item for item in turns if item["target"] == target.id]
                ids = {item["dataset_id"] for item in items}
                aggregates[target.id] = {
                    **_target_fields(target, config.model),
                    "turn_execution_accuracy": sum(item["score"]["exact_match"] for item in items)
                    / len(items)
                    if items
                    else 0,
                    "fully_correct_conversations": sum(
                        all(
                            i["score"]["exact_match"]
                            for i in items
                            if i["dataset_id"] == dataset_id
                        )
                        for dataset_id in ids
                    ),
                    "conversation_count": len(ids),
                    "mean_latency_seconds": sum(item["latency_seconds"] for item in items)
                    / len(items)
                    if items
                    else 0,
                }
            return {"config": vars(config), "aggregates": aggregates, "turns": turns}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay ConvFinQA conversations against the local API."
    )
    parser.add_argument("--base-url", default=DEFAULT_URL)
    parser.add_argument("--mode", choices=("direct", "remote"), default="direct")
    parser.add_argument("--dataset-ids", default="3139")
    parser.add_argument("--targets", default="baseline:v1,baseline-tool:v1,program-of-thought:v1")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--output-dir", type=Path, default=Path("eval-results"))
    parser.add_argument("--keep-sessions", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.dataset_ids = [int(item.strip()) for item in args.dataset_ids.split(",") if item.strip()]
    args.targets = [item.strip() for item in args.targets.split(",") if item.strip()]
    parse_targets(args.targets)
    return args


def main() -> None:
    config = _args()
    result = asyncio.run(run(config))
    print(json.dumps(result, indent=2, default=str))
    if not config.dry_run:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        (config.output_dir / "convfinqa.json").write_text(
            json.dumps(result, indent=2, default=str) + "\n"
        )
        lines = ["# ConvFinQA evaluation", "", f"Model: `{config.model}`", ""]
        for target, aggregate in result["aggregates"].items():
            lines.append(
                f"- **{target}**: {aggregate['turn_execution_accuracy']:.1%} turn accuracy; "
                f"{aggregate['fully_correct_conversations']}/{aggregate['conversation_count']} "
                "fully correct conversations; "
                f"mean latency {aggregate['mean_latency_seconds']:.2f}s"
            )
        lines.extend(["", "## Turn details", ""])
        for item in result["turns"]:
            score = item["score"]
            lines.extend(
                [
                    f"### Dataset {item['dataset_id']} · Turn {item['turn']} ({item['target']})",
                    f"- Question: {item['question']}",
                    f"- Expected: {item['expected']}",
                    f"- Actual: {item['actual']}",
                    f"- Match: {score['exact_match']}",
                    f"- Extraction: `{score['extraction_method']}` from "
                    f"`{score.get('extracted_text')}`",
                    f"- Normalized: expected `{score.get('expected')}`, actual "
                    f"`{score.get('actual')}`",
                    f"- Error: absolute `{score.get('absolute_error')}`, relative "
                    f"`{score.get('relative_error')}`",
                    "",
                ]
            )
        (config.output_dir / "convfinqa.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
