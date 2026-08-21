"""AG-UI event validation and collection helpers."""

from typing import Any

from pydantic import TypeAdapter

from evals.events_schema import (
    ExecutionEvent,
    IgnoredEvent,
    ModelUsageEvent,
    ModelUsageObservation,
    PendingToolCall,
    RunErrorEvent,
    TextEvent,
    ToolCall,
    ToolEvent,
)

__all__ = [
    "EventCollector",
    "ExecutionEvent",
    "IgnoredEvent",
    "ModelUsageEvent",
    "ModelUsageObservation",
    "PendingToolCall",
    "RunErrorEvent",
    "TextEvent",
    "ToolCall",
    "ToolEvent",
    "validate_event",
]

_EVENT_ADAPTER = TypeAdapter(ExecutionEvent)


def validate_event(value: Any) -> ExecutionEvent:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return _EVENT_ADAPTER.validate_python(value)


class EventCollector:
    def __init__(self) -> None:
        self.text: list[str] = []
        self.error: str | None = None
        self._tools: dict[str, PendingToolCall] = {}
        self.model_usage: tuple[ModelUsageObservation, ...] = ()
        self._sources: list[str | None] = []

    def add(self, event: Any) -> None:
        source = event.get("source") if isinstance(event, dict) else None
        parsed = validate_event(event)
        if isinstance(parsed, TextEvent):
            self.text.append(parsed.text)
            self._sources.append(source if isinstance(source, str) else None)
        elif isinstance(parsed, RunErrorEvent):
            self.error = parsed.message
        elif isinstance(parsed, ModelUsageEvent):
            self.model_usage += parsed.value.calls
        elif isinstance(parsed, ToolEvent):
            record = self._tools.setdefault(parsed.call_id, PendingToolCall(id=parsed.call_id))
            if parsed.name is not None:
                record.name = parsed.name
            if "ARGS" in parsed.type and parsed.arguments is not None:
                record.arguments += parsed.arguments
            if "RESULT" in parsed.type:
                record.result = parsed.result

    @property
    def tools(self) -> tuple[ToolCall, ...]:
        return tuple(ToolCall.model_validate(item.model_dump()) for item in self._tools.values())

    def assistant_text(self, *, ensemble: bool = False) -> str:
        """Return collected assistant text, preserving source-aware ensemble events."""
        if ensemble:
            selected = [
                text
                for text, source in zip(self.text, self._sources, strict=True)
                if source in {"ensemble", "reviewer"}
            ]
            if selected:
                return "".join(selected)
        return "".join(self.text)
