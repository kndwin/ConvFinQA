import asyncio
from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent, TextMessageContentEvent
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
        except asyncio.CancelledError, GeneratorExit:
            stream.cancel()
            raise
