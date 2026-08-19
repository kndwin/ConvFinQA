"""Temporal parent/child ensemble workflows using the Agents plugin Activities."""

import asyncio
from datetime import timedelta
from typing import Any, cast

from agents import Agent, RunConfig, Runner
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.contrib.workflow_streams import WorkflowStream
from temporalio.exceptions import ApplicationError
from temporalio.workflow import ChildWorkflowCancellationType, ParentClosePolicy

from src.module.agent_execution.agent_approach.ensemble.definition import (
    CandidateFailure,
    CandidateResult,
    render_reviewer_input,
)
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.execution.durable.durable_agent_workflow import DurableAgentWorkflow
from src.module.agent_execution.execution.durable.durable_agent_workflow_schema import (
    DurableAgentWorkflowInput,
)
from src.module.agent_execution.execution.durable.ensemble_workflow_schema import (
    EnsembleCandidateOutput,
    EnsembleFailureFinalizationInput,
    EnsembleFinalizationInput,
    EnsembleWorkflowInput,
    EnsembleWorkflowOutput,
)


@workflow.defn
class EnsembleWorkflow:
    @workflow.init
    def __init__(self, request: EnsembleWorkflowInput) -> None:
        self.stream = WorkflowStream()

    @workflow.run
    async def run(self, request: EnsembleWorkflowInput) -> EnsembleWorkflowOutput:
        # Starting and awaiting children is deliberately a separate phase.  A
        # ChildWorkflowHandle is not the child result; awaiting it only waits
        # for the child execution to complete.
        starts = [
            workflow.start_child_workflow(
                DurableAgentWorkflow.run,
                DurableAgentWorkflowInput(
                    execution_id=f"{workflow.info().workflow_id}:candidate:{candidate.approach}",
                    approach=candidate.approach,
                    model=candidate.model,
                    agent_name=candidate.name,
                    instructions=candidate.instructions,
                    rendered_context=candidate.rendered_context,
                    trace_metadata=candidate.trace_metadata,
                    prompt_version=candidate.prompt_version,
                    prompt_hash=candidate.prompt_hash,
                    context_version=candidate.context_version,
                    context_hash=candidate.context_hash,
                    stream=True,
                ),
                id=f"{workflow.info().workflow_id}:candidate:{candidate.approach}",
                task_queue=workflow.info().task_queue,
                parent_close_policy=ParentClosePolicy.TERMINATE,
                cancellation_type=ChildWorkflowCancellationType.WAIT_CANCELLATION_COMPLETED,
            )
            for candidate in request.candidates
        ]
        started_children = await asyncio.gather(*starts, return_exceptions=True)

        async def result_or_failure(index: int, value: object) -> EnsembleCandidateOutput:
            candidate = request.candidates[index]
            if isinstance(value, BaseException):
                return EnsembleCandidateOutput(
                    approach=candidate.approach,
                    status="failed",
                    error="candidate unavailable",
                    prompt_version=candidate.prompt_version,
                    prompt_hash=candidate.prompt_hash,
                    context_version=candidate.context_version,
                    context_hash=candidate.context_hash,
                    workflow_id=f"{workflow.info().workflow_id}:candidate:{candidate.approach}",
                )
            try:
                result = await cast(Any, value)
                if not hasattr(result, "final_output"):
                    raise TypeError("invalid candidate result")
                return EnsembleCandidateOutput(
                    approach=result.approach,
                    status="completed",
                    final_output=result.final_output,
                    duration_ms=result.duration_ms,
                    prompt_version=result.prompt_version,
                    prompt_hash=result.prompt_hash,
                    context_version=result.context_version,
                    context_hash=result.context_hash,
                    workflow_id=workflow.info().workflow_id + f":candidate:{candidate.approach}",
                )
            except Exception:
                return EnsembleCandidateOutput(
                    approach=candidate.approach,
                    status="failed",
                    error="candidate unavailable",
                    prompt_version=candidate.prompt_version,
                    prompt_hash=candidate.prompt_hash,
                    context_version=candidate.context_version,
                    context_hash=candidate.context_hash,
                    workflow_id=f"{workflow.info().workflow_id}:candidate:{candidate.approach}",
                )

        candidates = tuple(
            await asyncio.gather(
                *(result_or_failure(index, value) for index, value in enumerate(started_children))
            )
        )

        # Keep the canonical prompt formatting in the transport-neutral domain
        # module. The workflow DTO is intentionally converted at this boundary.
        domain_candidates = tuple(
            CandidateResult(
                approach=AgentApproach(item.approach),
                final_output=item.final_output,
                duration_ms=item.duration_ms,
            )
            if item.status == "completed"
            else CandidateFailure(
                approach=AgentApproach(item.approach),
                error="candidate unavailable",
                duration_ms=item.duration_ms,
            )
            for item in candidates
        )
        prompt = render_reviewer_input(request.context, request.question, domain_candidates)
        try:
            reviewer = Runner.run_streamed(
                Agent(
                    name="Ensemble independent reviewer",
                    instructions=request.reviewer_instructions,
                    model=request.reviewer_model,
                    tools=[],
                ),
                prompt,
                run_config=RunConfig(
                    workflow_name="ensemble-reviewer",
                    trace_metadata=request.trace_metadata,
                    trace_include_sensitive_data=False,
                ),
            )
            async for _ in reviewer.stream_events():
                pass
            output = reviewer.final_output
            if not isinstance(output, str) or not output.strip():
                raise ValueError("empty reviewer output")
        except Exception as exc:
            if request.finalization is not None:
                await workflow.execute_activity(
                    "fail-ensemble-run",
                    EnsembleFailureFinalizationInput(target=request.finalization),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            raise ApplicationError("reviewer could not complete", non_retryable=True) from exc
        result = EnsembleWorkflowOutput(
            reviewer_output=output,
            candidates=candidates,
            reviewer_prompt_version="ensemble-reviewer:v1",
        )
        if request.finalization is not None:
            await workflow.execute_activity(
                "finalize-ensemble-run",
                EnsembleFinalizationInput(target=request.finalization, output=result),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
        return result
