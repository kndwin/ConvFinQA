"""No-paid-call integration proof for the streamed Temporal ensemble."""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from unittest import IsolatedAsyncioTestCase

from agents import (
    AgentOutputSchemaBase,
    Handoff,
    Model,
    ModelResponse,
    ModelSettings,
    ModelTracing,
    Tool,
    TResponseInputItem,
    Usage,
)
from agents.items import TResponseStreamEvent
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseTextConfig,
    ResponseTextDeltaEvent,
    ResponseUsage,
)
from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails
from openai.types.shared.response_format_text import ResponseFormatText
from src.module.agent_execution.execution.durable.durable_agent_workflow import DurableAgentWorkflow
from src.module.agent_execution.execution.durable.ensemble_workflow import (
    EnsembleWorkflow,
)
from src.module.agent_execution.execution.durable.ensemble_workflow_schema import (
    EnsembleCandidateInput,
    EnsembleWorkflowInput,
)
from temporalio.contrib.openai_agents import ModelActivityParameters
from temporalio.contrib.openai_agents.testing import AgentEnvironment
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker


class _StreamingModel(Model):
    def _response(self) -> Response:
        output = ResponseOutputMessage(
            id="message",
            content=[
                ResponseOutputText(
                    text="ensemble proof", annotations=[], type="output_text", logprobs=[]
                )
            ],
            role="assistant",
            status="completed",
            type="message",
        )
        return Response(
            id="response",
            created_at=0,
            error=None,
            incomplete_details=None,
            instructions=None,
            metadata={},
            model="fake",
            object="response",
            output=[output],
            parallel_tool_calls=True,
            temperature=1.0,
            tool_choice="auto",
            tools=[],
            top_p=1.0,
            status="completed",
            text=ResponseTextConfig(format=ResponseFormatText(type="text")),
            truncation="disabled",
            usage=ResponseUsage(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                input_tokens_details=InputTokensDetails.model_validate(
                    {"cached_tokens": 0, "cache_write_tokens": 0}
                ),
                output_tokens_details=OutputTokensDetails(reasoning_tokens=0),
            ),
        )

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        **kwargs: Any,
    ) -> ModelResponse:
        return ModelResponse(output=self._response().output, usage=Usage(), response_id=None)

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        **kwargs: Any,
    ) -> AsyncIterator[TResponseStreamEvent]:
        yield ResponseTextDeltaEvent(
            content_index=0,
            delta="ensemble proof",
            item_id="message",
            output_index=0,
            sequence_number=0,
            type="response.output_text.delta",
            logprobs=[],
        )
        yield ResponseCompletedEvent(
            response=self._response(), sequence_number=1, type="response.completed"
        )


class TemporalEnsembleTests(IsolatedAsyncioTestCase):
    async def test_parent_runs_parallel_children_then_reviewer(self) -> None:
        params = ModelActivityParameters(
            start_to_close_timeout=timedelta(seconds=30),
            streaming_topic="agent-output",
        )
        candidates = tuple(
            EnsembleCandidateInput(
                approach=approach,
                name=approach,
                instructions="Answer directly.",
                rendered_context="Question context",
                model="fake",
                prompt_version=f"{approach}:v1",
                prompt_hash=f"{approach}-hash",
                context_version="document-conversation:v1",
                context_hash="context-hash",
            )
            for approach in ("baseline", "baseline-tool")
        )
        request = EnsembleWorkflowInput(
            question="What is the answer?",
            context="Question context",
            candidates=candidates,
            reviewer_instructions="Verify and answer.",
            reviewer_model="fake",
        )
        async with (
            await WorkflowEnvironment.start_time_skipping() as environment,
            AgentEnvironment(model=_StreamingModel(), model_params=params) as agents,
        ):
            client = agents.applied_on_client(environment.client)
            async with Worker(
                client,
                task_queue="ensemble-tests",
                workflows=[EnsembleWorkflow, DurableAgentWorkflow],
            ):
                result = await client.execute_workflow(
                    EnsembleWorkflow.run,
                    request,
                    id="ensemble-test",
                    task_queue="ensemble-tests",
                    execution_timeout=timedelta(seconds=30),
                )

        self.assertEqual(result.reviewer_output, "ensemble proof")
        self.assertEqual(
            [item.approach for item in result.candidates], ["baseline", "baseline-tool"]
        )
        self.assertTrue(all(item.status == "completed" for item in result.candidates))
        self.assertTrue(all(item.workflow_id for item in result.candidates))
