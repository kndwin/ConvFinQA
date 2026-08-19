"""Reusable single-agent durable primitive."""

from datetime import timedelta

from agents import RunConfig, Runner
from temporalio import workflow
from temporalio.contrib.workflow_streams import WorkflowStream
from temporalio.exceptions import ApplicationError

from src.module.agent_execution.agent_approach.shared.agent_definition import build_agent
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.execution.durable.durable_agent_workflow_schema import (
    DurableAgentWorkflowInput,
    DurableAgentWorkflowResult,
)


@workflow.defn
class DurableAgentWorkflow:
    @workflow.init
    def __init__(self, request: DurableAgentWorkflowInput) -> None:
        self.stream = WorkflowStream()

    @workflow.run
    async def run(self, request: DurableAgentWorkflowInput) -> DurableAgentWorkflowResult:
        started = workflow.now()
        agent, default_max_turns = build_agent(
            AgentApproach(request.approach),
            name=request.agent_name,
            instructions=request.instructions,
            model=request.model,
        )
        run_config = RunConfig(
            workflow_name="DurableAgentWorkflow",
            group_id=request.execution_id,
            trace_metadata=request.trace_metadata,
            trace_include_sensitive_data=False,
        )
        if request.stream:
            streamed = Runner.run_streamed(
                agent,
                request.rendered_context,
                max_turns=request.max_turns or default_max_turns,
                run_config=run_config,
            )
            async for _ in streamed.stream_events():
                pass
            result = streamed
        else:
            result = await Runner.run(
                agent,
                request.rendered_context,
                max_turns=request.max_turns or default_max_turns,
                run_config=run_config,
            )
        if not isinstance(result.final_output, str) or not result.final_output.strip():
            raise ApplicationError(
                "Durable agent returned an empty or non-string final output",
                non_retryable=True,
            )
        return DurableAgentWorkflowResult(
            execution_id=request.execution_id,
            final_output=result.final_output,
            approach=request.approach,
            duration_ms=max(0, int((workflow.now() - started) / timedelta(milliseconds=1))),
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            context_version=request.context_version,
            context_hash=request.context_hash,
        )
