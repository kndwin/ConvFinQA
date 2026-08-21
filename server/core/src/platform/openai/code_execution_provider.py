import json
from typing import Any, cast

from agents import CodeInterpreterTool
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import RunItemStreamEvent

from src.module.agent_execution.agent_approach.shared.tools.code_execution.provider import (
    CodeExecutionProvider,
    CodeExecutionSnapshot,
    CodeExecutionUpdate,
)


def _is_code_interpreter_item(item: object) -> bool:
    return getattr(item, "type", None) == "code_interpreter_call"


def _output_text(outputs: object) -> str:
    if isinstance(outputs, list):
        values = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in outputs
        ]
        return json.dumps(values, sort_keys=True)
    return str(outputs)


class OpenAICodeExecutionProvider(CodeExecutionProvider):
    def tool(self) -> CodeInterpreterTool:
        # The Responses API provisions and disposes an ephemeral hosted container.
        return CodeInterpreterTool({"type": "code_interpreter", "container": {"type": "auto"}})

    def normalize_raw_event(self, event: object) -> CodeExecutionUpdate | None:
        raw = cast(Any, event)
        event_type = getattr(raw, "type", "")
        if event_type == "response.output_text.delta":
            delta = getattr(raw, "delta", "")
            return CodeExecutionUpdate(kind="text_delta", delta=delta) if delta else None
        if event_type == "response.code_interpreter_call_code.delta":
            call_id = str(getattr(raw, "item_id", ""))
            if not call_id:
                return None
            return CodeExecutionUpdate(
                kind="code_delta", call_id=call_id, tool_name="code_interpreter", delta=raw.delta
            )
        if event_type == "response.code_interpreter_call.completed":
            call_id = str(getattr(raw, "item_id", "") or getattr(raw, "id", ""))
            if not call_id:
                return None
            return self._snapshot(raw, call_id)
        if event_type == "response.output_item.done" and _is_code_interpreter_item(
            getattr(raw, "item", None)
        ):
            item = raw.item
            return self._snapshot(item, item.id)
        return None

    def normalize_run_item_event(self, event: object) -> CodeExecutionUpdate | None:
        if not isinstance(event, RunItemStreamEvent):
            return None
        if event.name == "tool_called" and isinstance(event.item, ToolCallItem):
            raw = event.item.raw_item
            if not _is_code_interpreter_item(raw):
                return None
            call_id = raw.get("id") if isinstance(raw, dict) else getattr(raw, "id", None)
            if not call_id:
                return None
            return self._snapshot(raw, str(call_id))
        if event.name == "tool_output" and isinstance(event.item, ToolCallOutputItem):
            raw = event.item.raw_item
            call_id = (
                raw.get("call_id", raw.get("tool_call_id"))
                if isinstance(raw, dict)
                else getattr(raw, "call_id", getattr(raw, "tool_call_id", None))
            )
            if call_id:
                return CodeExecutionUpdate(
                    kind="tool_output", call_id=str(call_id), output=str(event.item.output)
                )
        return None

    def _snapshot(self, raw: object, call_id: str) -> CodeExecutionUpdate:
        outputs = getattr(raw, "outputs", None)
        snapshot = CodeExecutionSnapshot(
            call_id=call_id,
            tool_name="code_interpreter",
            status=getattr(raw, "status", None) or "completed",
            code=getattr(raw, "code", None),
            output=_output_text(outputs) if outputs else None,
        )
        return CodeExecutionUpdate(kind="snapshot", snapshot=snapshot)
