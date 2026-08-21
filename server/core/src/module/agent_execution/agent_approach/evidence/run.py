import asyncio
import json
import math
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from typing import Any

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
from pydantic import TypeAdapter

from src.module.agent_execution.agent_approach.evidence.structured_output import EvidenceAnswer
from src.module.agent_execution.agent_approach.shared.agent_builder import build_agent
from src.module.agent_execution.agent_approach.shared.base_agent_approach import BaseAgentApproach
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import (
    ApproachInput,
    PromptVersion,
    RenderedContext,
)

from .context.registry import resolve as resolve_context
from .index import index_document
from .output_guardrail import evidence_output_guardrail
from .prompts.registry import resolve as resolve_prompt
from .tools import EvidenceToolState, evidence_fetch, grounded_calculator

_JSON_ADAPTER = TypeAdapter(Any)


def _serialize_tool_result(output) -> str:
    """Return a stable JSON representation of a tool result.

    The SDK can expose output as a model, a mapping, or (for some tools) an
    already serialized JSON string.  Parsing strings first avoids turning a
    JSON object into a JSON string, while ``default=str`` keeps Decimal values
    lossless and ``allow_nan=False`` keeps the result strict JSON.
    """
    if isinstance(output, str):
        with suppress(json.JSONDecodeError):
            output = json.loads(output)
    _reject_non_finite(output)
    output = _JSON_ADAPTER.dump_python(output, mode="json")
    return json.dumps(
        output,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
        default=str,
    )


def _reject_non_finite(value) -> None:
    """Reject floats before Pydantic's JSON mode turns them into null."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Out of range float values are not JSON compliant")
    elif isinstance(value, Mapping):
        for item in value.values():
            _reject_non_finite(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _reject_non_finite(item)
    elif hasattr(value, "model_dump"):
        _reject_non_finite(value.model_dump(mode="python"))
    elif hasattr(value, "__dataclass_fields__"):
        for name in value.__dataclass_fields__:
            _reject_non_finite(getattr(value, name))


class EvidenceApproach(BaseAgentApproach):
    def resolve_prompt(self, prompt_id: str = "evidence:v1") -> PromptVersion:
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
        state = EvidenceToolState(index_document(input_data.document))
        agent = build_agent(
            name="ConvFinQA evidence assistant",
            model=input_data.model,
            instructions=input_data.prompt.instructions,
            tools=[evidence_fetch, grounded_calculator],
            require_tool=True,
            output_type=EvidenceAnswer,
            output_guardrails=[evidence_output_guardrail],
        )
        return self._events_evidence(
            input_data,
            self._stream(input_data, agent, 8, "ConvFinQA evidence chat", run_context=state),
        )

    async def _events_evidence(
        self, data: ApproachInput, stream: RunResultStreaming
    ) -> AsyncIterator[BaseEvent]:
        try:
            async for event in stream.stream_events():
                if (
                    isinstance(event, RunItemStreamEvent)
                    and event.name == "tool_called"
                    and isinstance(event.item, ToolCallItem)
                ):
                    cid = event.item.call_id
                    if cid:
                        yield ToolCallStartEvent(
                            tool_call_id=str(cid),
                            tool_call_name=str(event.item.tool_name or ""),
                            parent_message_id=data.assistant_message_id,
                        )
                        yield ToolCallArgsEvent(
                            tool_call_id=str(cid),
                            delta=str(
                                event.item.raw_item.get("arguments", "")
                                if isinstance(event.item.raw_item, Mapping)
                                else getattr(event.item.raw_item, "arguments", "")
                            ),
                        )
                        yield ToolCallEndEvent(tool_call_id=str(cid))
                elif (
                    isinstance(event, RunItemStreamEvent)
                    and event.name == "tool_output"
                    and isinstance(event.item, ToolCallOutputItem)
                ):
                    cid = event.item.call_id
                    if cid:
                        yield ToolCallResultEvent(
                            message_id=str(uuid.uuid4()),
                            tool_call_id=str(cid),
                            content=_serialize_tool_result(event.item.output),
                            role="tool",
                        )
            final = stream.final_output
            if not isinstance(final, EvidenceAnswer):
                raise RuntimeError("Invalid structured final output")
            yield TextMessageContentEvent(
                message_id=data.assistant_message_id,
                delta=json.dumps(
                    final.model_dump(mode="json", exclude_none=True),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
            usage = self._model_usage_event(data, stream)
            if usage:
                yield usage
        except asyncio.CancelledError, GeneratorExit:
            stream.cancel()
            raise
