import json
import time
from contextlib import suppress
from typing import Any
from uuid import uuid4

import httpx
from ag_ui.core import RunAgentInput, UserMessage

from evals.models_schema import (
    ConversationCase,
    EvaluationConfig,
    ModelUsageObservation,
    ObservedTurn,
    TargetSpec,
    ToolCall,
)


class EventCollector:
    def __init__(self) -> None:
        self.text: list[str] = []
        self.error: str | None = None
        self._tools: dict[str, dict[str, str | None]] = {}
        self.model_usage: tuple[ModelUsageObservation, ...] = ()

    def add(self, event: Any) -> None:
        data = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        if not isinstance(data, dict):
            return
        kind = str(data.get("type", "")).upper()
        if kind in {"TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_CHUNK"}:
            value = data.get("delta") or data.get("content") or data.get("text")
            if isinstance(value, str):
                self.text.append(value)
        elif kind == "RUN_ERROR":
            self.error = str(data.get("message") or data.get("error") or data)
        elif kind == "CUSTOM" and data.get("name") == "model_usage":
            value = data.get("value")
            if isinstance(value, dict):
                calls = value.get("calls")
                if isinstance(calls, list):
                    self.model_usage += tuple(
                        ModelUsageObservation.model_validate(call) for call in calls
                    )
                else:
                    self.model_usage += (ModelUsageObservation.model_validate(value),)
        elif kind.startswith("TOOL_CALL"):
            call_id = str(data.get("tool_call_id") or data.get("id") or "unknown")
            record = self._tools.setdefault(
                call_id, {"name": None, "arguments": "", "result": None}
            )
            name = data.get("tool_call_name") or data.get("name")
            if isinstance(name, str):
                record["name"] = name
            if "ARGS" in kind:
                fragment = data.get("delta") or data.get("args") or data.get("arguments")
                if fragment is not None:
                    record["arguments"] = str(record["arguments"] or "") + str(fragment)
            if "RESULT" in kind:
                result = data.get("content") or data.get("result")
                record["result"] = None if result is None else str(result)

    @property
    def tools(self) -> tuple[ToolCall, ...]:
        return tuple(
            ToolCall(
                id=call_id,
                name=values["name"],
                arguments=str(values["arguments"] or ""),
                result=values["result"],
            )
            for call_id, values in self._tools.items()
        )


def parse_sse(lines: list[str]) -> tuple[dict[str, Any], ...]:
    events: list[dict[str, Any]] = []
    fragments: list[str] = []

    def flush() -> None:
        if not fragments:
            return
        raw = "".join(fragments)
        fragments.clear()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return
        if isinstance(value, dict):
            events.append(value)

    for line in lines:
        if line.startswith("data:"):
            fragments.append(line[5:].strip())
        elif not line:
            flush()
    flush()
    return tuple(events)


async def execute_direct(
    case: ConversationCase, target: TargetSpec, config: EvaluationConfig
) -> tuple[ObservedTurn, ...]:
    from src.module.agent_execution.agent_execution_constants import OpenAIModel
    from src.module.agent_execution.agent_execution_repository import (
        InMemoryAgentExecutionRepository,
    )
    from src.module.agent_execution.agent_execution_service import AgentExecutionService
    from src.module.agent_execution.agent_execution_service_schema import (
        AgentExecutionServiceRunParams,
    )
    from src.platform.openai import openai_client

    repository = InMemoryAgentExecutionRepository()
    observations = []
    thread_id = f"eval:{case.dataset_id}:{target.id}"
    async with openai_client() as client:
        service = AgentExecutionService(client)
        for number, expected in enumerate(case.turns, 1):
            run_id = str(uuid4())
            collector = EventCollector()
            started = time.perf_counter()
            params = AgentExecutionServiceRunParams(
                approach=target.approach,
                prompt_version=None,
                context_version=target.context_version,
                document=case.document,
                prompt_override=target.prompt,
                model=OpenAIModel(config.application_model),
                input_data=RunAgentInput(
                    thread_id=thread_id,
                    run_id=run_id,
                    state={},
                    messages=[UserMessage(id=str(uuid4()), content=expected.question)],
                    tools=[],
                    context=[],
                    forwarded_props={},
                ),
                trace_metadata={
                    "evaluation_dataset_id": str(case.dataset_id),
                    "evaluation_target": target.id,
                },
            )
            async for event in service.run(params, repository):
                collector.add(event)
            if collector.error:
                raise RuntimeError(collector.error)
            actual = "".join(collector.text)
            if not actual.strip():
                raise RuntimeError("Evaluation turn produced no assistant text")
            observations.append(
                ObservedTurn(
                    turn=number,
                    question=expected.question,
                    expected=expected.answer,
                    actual=actual,
                    latency_seconds=time.perf_counter() - started,
                    run_id=run_id,
                    thread_id=thread_id,
                    tools=collector.tools,
                    model_usage=collector.model_usage,
                )
            )
    return tuple(observations)


async def execute_remote(
    case: ConversationCase, target: TargetSpec, config: EvaluationConfig
) -> tuple[ObservedTurn, ...]:
    base_url = str(config.base_url).rstrip("/")
    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        response = await client.post(
            f"/dataset-conversations/{case.dataset_id}/chat-sessions",
            json={"agent_approach": str(target.approach), "model": config.application_model},
        )
        response.raise_for_status()
        session = response.json()
        expected_fields = {
            "agent_approach": str(target.approach),
            "prompt_version": target.prompt.id,
            "context_version": target.context_version,
            "model": config.application_model,
        }
        session_id = str(session["id"])
        messages: list[dict[str, Any]] = []
        observations = []
        original_error: BaseException | None = None
        try:
            for key, expected_value in expected_fields.items():
                if str(session.get(key)) != expected_value:
                    raise RuntimeError(f"Created session {key} does not match target")
            for number, expected in enumerate(case.turns, 1):
                run_id = str(uuid4())
                messages.append(
                    UserMessage(id=str(uuid4()), content=expected.question).model_dump(mode="json")
                )
                payload = RunAgentInput(
                    thread_id=session_id,
                    run_id=run_id,
                    state={},
                    messages=messages,
                    tools=[],
                    context=[],
                    forwarded_props={},
                )
                started = time.perf_counter()
                async with client.stream(
                    "POST",
                    f"/dataset-conversations/{case.dataset_id}/chat-sessions/{session_id}/runs",
                    json=payload.model_dump(mode="json"),
                    headers={"Accept": "text/event-stream"},
                ) as stream:
                    stream.raise_for_status()
                    collector = EventCollector()
                    for event in parse_sse([line async for line in stream.aiter_lines()]):
                        collector.add(event)
                if collector.error:
                    raise RuntimeError(collector.error)
                actual = "".join(collector.text)
                if not actual.strip():
                    raise RuntimeError("Evaluation turn produced no assistant text")
                messages.append({"id": str(uuid4()), "role": "assistant", "content": actual})
                observations.append(
                    ObservedTurn(
                        turn=number,
                        question=expected.question,
                        expected=expected.answer,
                        actual=actual,
                        latency_seconds=time.perf_counter() - started,
                        run_id=run_id,
                        thread_id=session_id,
                        session_id=session_id,
                        tools=collector.tools,
                        model_usage=collector.model_usage,
                    )
                )
        except BaseException as exc:
            original_error = exc
            raise
        finally:
            if not config.keep_sessions:
                if original_error is not None:
                    with suppress(Exception):
                        await client.delete(
                            f"/dataset-conversations/{case.dataset_id}/chat-sessions/{session_id}"
                        )
                else:
                    cleanup = await client.delete(
                        f"/dataset-conversations/{case.dataset_id}/chat-sessions/{session_id}"
                    )
                    cleanup.raise_for_status()
    return tuple(observations)
