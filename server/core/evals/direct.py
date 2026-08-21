"""Direct execution through the production application service."""

import time
from typing import Any
from uuid import uuid4

from ag_ui.core import RunAgentInput, UserMessage

from evals.benchmarks.convfinqa.cases_schema import ConversationCase
from evals.config_schema import EvaluationConfig
from evals.direct_schema import ObservedTurn
from evals.events import EventCollector
from evals.targets_schema import TargetSpec


async def execute_direct(
    case: ConversationCase, target: TargetSpec, config: EvaluationConfig
) -> tuple[ObservedTurn, ...]:
    if target.id in {"program-of-thought:v3"}:
        return await _execute_staged(case, target, config)
    from src.module.agent_execution.agent_execution_constants import OpenAIModel
    from src.module.agent_execution.agent_execution_repository import (
        InMemoryAgentExecutionRepository,
    )
    from src.module.agent_execution.agent_execution_service import AgentExecutionService
    from src.module.agent_execution.agent_execution_service_schema import (
        AgentExecutionServiceRunParams,
    )
    from src.platform.openai import model_provider
    from src.platform.openai.code_execution_provider import OpenAICodeExecutionProvider

    repository = InMemoryAgentExecutionRepository()
    observations = []
    thread_id = f"eval:{case.dataset_id}:{target.id}"
    # Keep the eval executor on the same application-owned provider lifecycle as
    # the API composition root.  In particular, model_provider owns the
    # AsyncOpenAI client's cleanup and may yield None when no key is configured.
    async with model_provider() as provider:
        service = AgentExecutionService(provider, OpenAICodeExecutionProvider())
        for number, expected in enumerate(case.turns, 1):
            run_id = str(uuid4())
            collector = EventCollector()
            started = time.perf_counter()
            params = AgentExecutionServiceRunParams(
                approach=target.approach,
                prompt_version=None,
                context_version=target.context_version,
                # Keep the benchmark document on the production service path;
                # the service prepares the context expected by all approaches.
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
            # Structured targets turn provider/output failures into invalid artifacts.
            actual = collector.assistant_text(ensemble=target.ensemble_config is not None)
            if not actual.strip() and target.id not in {"baseline:v3", "evidence:v1"}:
                raise RuntimeError("Evaluation turn produced no assistant text")
            structured = None
            if target.id == "baseline:v3":
                from evals.benchmarks.convfinqa.structured import process_output

                structured = process_output(target.id, actual, expected.question)
                if collector.error:
                    structured.update(valid=False, validation_error=collector.error)
            elif target.id == "evidence:v1":
                from evals.benchmarks.convfinqa.structured import process_evidence_output

                structured = process_evidence_output(
                    target.id, actual, expected.question, collector
                )
                from src.module.agent_execution.agent_approach.evidence.index import (
                    index_document,
                    index_hash,
                )

                structured["index_hash"] = index_hash(index_document(case.document))
                if collector.error:
                    structured.update(valid=False, validation_error=collector.error)
            observations.append(
                ObservedTurn(
                    turn=number,
                    question=expected.question,
                    expected=expected.answer,
                    executed_answer=expected.executed_answer,
                    turn_program=expected.turn_program,
                    qa_split=expected.qa_split,
                    actual=actual,
                    latency_seconds=time.perf_counter() - started,
                    run_id=run_id,
                    thread_id=thread_id,
                    tools=collector.tools,
                    model_usage=collector.model_usage,
                    structured=structured,
                )
            )
    return tuple(observations)


async def _execute_staged(case: ConversationCase, target: TargetSpec, config: EvaluationConfig):
    """Two hard calls: indexed document selection, then evidence-only action."""
    import json

    from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
    from src.module.agent_execution.agent_execution_repository import (
        InMemoryAgentExecutionRepository,
    )
    from src.module.agent_execution.agent_execution_service import AgentExecutionService
    from src.module.agent_execution.agent_execution_service_schema import (
        AgentExecutionServiceRunParams,
    )
    from src.platform.openai import model_provider
    from src.platform.openai.code_execution_provider import OpenAICodeExecutionProvider

    from evals.benchmarks.convfinqa.selector_prompt import EVIDENCE_SELECTOR_V1
    from evals.benchmarks.convfinqa.structured import (
        index_document,
        stage1_request,
        stage2_request,
        validate_stage1,
    )

    observations = []
    index = index_document(json.loads(case.document))
    async with model_provider() as provider:
        service = AgentExecutionService(provider, OpenAICodeExecutionProvider())
        for number, expected in enumerate(case.turns, 1):

            async def call(question: str, document: str, prompt: Any, stage: str, turn_number: int):
                started = time.perf_counter()
                stage_repository = InMemoryAgentExecutionRepository()
                collector = EventCollector()
                run_id = str(uuid4())
                params = AgentExecutionServiceRunParams(
                    approach=AgentApproach.BASELINE if stage == "evidence" else target.approach,
                    prompt_version=None,
                    context_version=target.context_version,
                    document=document,
                    prompt_override=prompt,
                    model=OpenAIModel(config.application_model),
                    input_data=RunAgentInput(
                        thread_id=f"eval:{case.dataset_id}:{target.id}:{stage}:{turn_number}",
                        run_id=run_id,
                        state={},
                        messages=[UserMessage(id=str(uuid4()), content=question)],
                        tools=[],
                        context=[],
                        forwarded_props={},
                    ),
                    trace_metadata={
                        "evaluation_dataset_id": case.dataset_id,
                        "evaluation_target": target.id,
                        "stage": stage,
                    },
                )
                async for event in service.run(params, stage_repository):
                    collector.add(event)
                return collector, run_id, time.perf_counter() - started

            history = [
                {
                    "turn": item.turn,
                    "question": item.question,
                    "result": (item.structured or {}).get("canonical")
                    if item.structured and item.structured.get("valid")
                    else None,
                    "status": "valid"
                    if item.structured and item.structured.get("valid")
                    else "invalid",
                }
                for item in observations
            ]
            prior = {
                str(item.turn): (item.structured or {}).get("canonical", {}).get("value")
                for item in observations
                if item.structured
                and item.structured.get("valid")
                and (item.structured.get("canonical") or {}).get("kind") == "number"
            }
            first, _, first_latency = await call(
                stage1_request(expected.question, history, index),
                json.dumps([x.model_dump(mode="json") for x in index], sort_keys=True),
                EVIDENCE_SELECTOR_V1,
                "evidence",
                number,
            )
            raw_ids = first.assistant_text()
            selected = ()
            stage_validation_error = None
            try:
                if first.error:
                    raise ValueError(f"evidence stage error: {first.error}")
                if not raw_ids.strip():
                    raise ValueError("evidence stage returned empty output")
                selected = validate_stage1(raw_ids, index)
                second, run_id, second_latency = await call(
                    stage2_request(expected.question, history, selected),
                    json.dumps([x.model_dump(mode="json") for x in selected], sort_keys=True),
                    target.prompt,
                    "action",
                    number,
                )
                actual = second.assistant_text()
                if second.error:
                    raise ValueError(f"action stage error: {second.error}")
                if not actual.strip():
                    raise ValueError("action stage returned empty output")
                tools = first.tools + second.tools
                usage = first.model_usage + second.model_usage
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                actual, run_id, tools, usage = "", str(uuid4()), first.tools, first.model_usage
                second_latency = 0
                stage_validation_error = str(exc)
            if not actual.strip():
                actual = ""
            from evals.benchmarks.convfinqa.structured import process_output

            artifact = process_output(
                target.id, actual, expected.question, selected=selected, prior=prior
            )
            artifact.update(
                raw_evidence_stage=raw_ids,
                selected_evidence=[item.model_dump(mode="json") for item in selected],
                stage_validation_error=stage_validation_error,
                action_validation_error=artifact.get("validation_error")
                if not artifact.get("valid", False)
                else None,
            )
            observations.append(
                ObservedTurn(
                    turn=number,
                    question=expected.question,
                    expected=expected.answer,
                    executed_answer=expected.executed_answer,
                    turn_program=expected.turn_program,
                    qa_split=expected.qa_split,
                    actual=actual,
                    latency_seconds=first_latency + second_latency,
                    run_id=run_id,
                    thread_id=f"eval:{case.dataset_id}:{target.id}",
                    tools=tools,
                    model_usage=usage,
                    structured=artifact,
                )
            )
    return tuple(observations)
