import asyncio
from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent, CustomEvent, TextMessageContentEvent
from agents import Agent, RunConfig, Runner, RunResultStreaming
from agents.models.openai_provider import OpenAIProvider
from agents.tracing.config import TracingConfig
from openai import AsyncOpenAI

from src.module.agent_execution.agent_execution_runner_schema import ApproachInput


class AgentsApproach:
    def __init__(self, client: AsyncOpenAI | None) -> None:
        self.client = client

    def _stream(
        self, data: ApproachInput, agent: Agent, max_turns: int, workflow: str
    ) -> RunResultStreaming:
        if self.client is None:
            raise RuntimeError("The assistant is not configured on the server")
        return Runner.run_streamed(
            agent,
            data.context.rendered,
            max_turns=max_turns,
            run_config=RunConfig(
                model=data.model,
                model_provider=OpenAIProvider(openai_client=self.client),
                workflow_name=workflow,
                group_id=data.trace_metadata.get(
                    "chat_session_id", data.trace_metadata.get("conversation_id", "")
                ),
                trace_metadata=data.trace_metadata,
                trace_include_sensitive_data=False,
                tracing=TracingConfig(include_task_and_turn_spans=True),
            ),
        )

    @staticmethod
    def _model_usage_event(data: ApproachInput, stream: RunResultStreaming) -> CustomEvent | None:
        """Convert the completed SDK usage into one event, preserving each request."""
        usage = getattr(getattr(stream, "context_wrapper", None), "usage", None)
        if usage is None:
            return None
        if not (usage.total_tokens or usage.input_tokens or usage.output_tokens):
            return None
        calls = [
            {
                "model": str(data.model),
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "total_tokens": item.total_tokens,
                "cached_input_tokens": getattr(item.input_tokens_details, "cached_tokens", None),
                "cache_write_tokens": getattr(
                    item.input_tokens_details, "cache_write_tokens", None
                ),
                "reasoning_tokens": getattr(item.output_tokens_details, "reasoning_tokens", None),
            }
            for item in usage.request_usage_entries
        ]
        if not calls:
            calls = [
                {
                    "model": str(data.model),
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "cached_input_tokens": getattr(
                        usage.input_tokens_details, "cached_tokens", None
                    ),
                    "cache_write_tokens": getattr(
                        usage.input_tokens_details, "cache_write_tokens", None
                    ),
                    "reasoning_tokens": getattr(
                        usage.output_tokens_details, "reasoning_tokens", None
                    ),
                }
            ]
        return CustomEvent(name="model_usage", value={"calls": calls})

    async def _events(
        self, data: ApproachInput, stream: RunResultStreaming
    ) -> AsyncIterator[BaseEvent]:
        try:
            answer = ""
            async for event in stream.stream_events():
                if (
                    event.type == "raw_response_event"
                    and getattr(event.data, "type", "") == "response.output_text.delta"
                ):
                    delta = getattr(event.data, "delta", "")
                    if delta:
                        answer += delta
                        yield TextMessageContentEvent(
                            message_id=data.assistant_message_id, delta=delta
                        )
            if (
                not isinstance(stream.final_output, str)
                or not stream.final_output.strip()
                or answer != stream.final_output
            ):
                raise RuntimeError("Invalid final output")
            usage_event = self._model_usage_event(data, stream)
            if usage_event is not None:
                yield usage_event
        except asyncio.CancelledError, GeneratorExit:
            stream.cancel()
            raise
