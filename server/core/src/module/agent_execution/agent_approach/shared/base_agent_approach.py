import asyncio
import json
from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent, CustomEvent, TextMessageContentEvent
from agents import Agent, RunConfig, Runner, RunResultStreaming
from agents.models.interface import ModelProvider
from agents.tracing.config import TracingConfig
from src.module.agent_execution.agent_execution_runner_schema import ApproachInput


class BaseAgentApproach:
    def __init__(self, model_provider: ModelProvider | None) -> None:
        self.model_provider = model_provider

    @property
    def is_configured(self) -> bool:
        return self.model_provider is not None

    def _stream(
        self,
        data: ApproachInput,
        agent: Agent,
        max_turns: int,
        workflow: str,
        run_context: object | None = None,
    ) -> RunResultStreaming:
        if self.model_provider is None:
            raise RuntimeError("The assistant is not configured on the server")
        run_config = RunConfig(
            model=data.model,
            model_provider=self.model_provider,
            workflow_name=workflow,
            group_id=data.trace_metadata.get(
                "chat_session_id", data.trace_metadata.get("conversation_id", "")
            ),
            trace_metadata=data.trace_metadata,
            trace_include_sensitive_data=False,
            tracing=TracingConfig(include_task_and_turn_spans=True),
        )
        if run_context is None:
            return Runner.run_streamed(
                agent, data.context.rendered, max_turns=max_turns, run_config=run_config
            )
        return Runner.run_streamed(
            agent,
            data.context.rendered,
            max_turns=max_turns,
            run_config=run_config,
            context=run_context,
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

    async def _events_structured(
        self, data: ApproachInput, stream: RunResultStreaming
    ) -> AsyncIterator[BaseEvent]:
        """Emit one canonical JSON assistant payload for SDK structured output."""
        try:
            async for _event in stream.stream_events():
                # Structured output may expose deltas that are not valid JSON;
                # intentionally do not forward them as assistant text.
                pass
            final = stream.final_output
            if hasattr(final, "model_dump"):
                payload = final.model_dump(mode="json", exclude_none=True)
            elif isinstance(final, dict):
                payload = final
            else:
                raise RuntimeError("Invalid structured final output")
            text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            yield TextMessageContentEvent(message_id=data.assistant_message_id, delta=text)
            usage_event = self._model_usage_event(data, stream)
            if usage_event is not None:
                yield usage_event
        except asyncio.CancelledError, GeneratorExit:
            stream.cancel()
            raise
