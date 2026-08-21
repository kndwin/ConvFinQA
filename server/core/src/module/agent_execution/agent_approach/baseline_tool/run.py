import asyncio
import uuid
from collections.abc import AsyncIterator

from ag_ui.core import (
    BaseEvent,
    TextMessageContentEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from agents import RunResultStreaming
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import RunItemStreamEvent
from src.module.agent_execution.agent_approach.baseline_tool.context.registry import (
    resolve as resolve_context,
)
from src.module.agent_execution.agent_approach.baseline_tool.prompts.registry import (
    resolve as resolve_prompt,
)
from src.module.agent_execution.agent_approach.baseline_tool.tools.calculator import calculator
from src.module.agent_execution.agent_approach.shared.agent_builder import build_agent
from src.module.agent_execution.agent_approach.shared.base_agent_approach import BaseAgentApproach
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import (
    ApproachInput,
    PromptVersion,
    RenderedContext,
)


class BaselineToolApproach(BaseAgentApproach):
    def resolve_prompt(self, prompt_id: str = "baseline-tool:v1") -> PromptVersion:
        return resolve_prompt(prompt_id)

    def render_context(
        self,
        version: str,
        document: str,
        transcript: tuple[ConversationMessage, ...],
        question: str,
    ) -> RenderedContext:
        return resolve_context(version, document, transcript, question)

    def stream(self, input_data: ApproachInput) -> AsyncIterator[BaseEvent]:
        agent = build_agent(
            name="ConvFinQA baseline-tool document assistant",
            model=input_data.model,
            instructions=input_data.prompt.instructions,
            tools=[calculator],
            require_tool=True,
        )
        return self._events_with_tools(
            input_data,
            self._stream(input_data, agent, 4, "ConvFinQA baseline-tool document chat"),
        )

    async def _events_with_tools(
        self, data: ApproachInput, stream: RunResultStreaming
    ) -> AsyncIterator[BaseEvent]:
        answer = ""
        try:
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
                elif (
                    isinstance(event, RunItemStreamEvent)
                    and event.name == "tool_called"
                    and isinstance(event.item, ToolCallItem)
                ):
                    raw = event.item.raw_item
                    call_id = (
                        raw.get("call_id", raw.get("tool_call_id"))
                        if isinstance(raw, dict)
                        else getattr(raw, "call_id", getattr(raw, "tool_call_id", None))
                    )
                    name = (
                        raw.get("name", "") if isinstance(raw, dict) else getattr(raw, "name", "")
                    )
                    arguments = (
                        raw.get("arguments", "")
                        if isinstance(raw, dict)
                        else getattr(raw, "arguments", "")
                    )
                    if not call_id:
                        continue
                    yield ToolCallStartEvent(
                        tool_call_id=str(call_id),
                        tool_call_name=str(name),
                        parent_message_id=data.assistant_message_id,
                    )
                    yield ToolCallArgsEvent(tool_call_id=str(call_id), delta=str(arguments))
                    yield ToolCallEndEvent(tool_call_id=str(call_id))
                elif (
                    isinstance(event, RunItemStreamEvent)
                    and event.name == "tool_output"
                    and isinstance(event.item, ToolCallOutputItem)
                ):
                    raw = event.item.raw_item
                    call_id = (
                        raw.get("call_id", raw.get("tool_call_id"))
                        if isinstance(raw, dict)
                        else getattr(raw, "call_id", getattr(raw, "tool_call_id", None))
                    )
                    if call_id:
                        yield ToolCallResultEvent(
                            message_id=str(uuid.uuid4()),
                            tool_call_id=str(call_id),
                            content=str(event.item.output),
                            role="tool",
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
