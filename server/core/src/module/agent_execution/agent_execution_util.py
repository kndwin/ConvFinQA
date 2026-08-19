"""Shared helpers for normalizing AG-UI execution input."""

from ag_ui.core import RunAgentInput
from pydantic import ValidationError

from src.module.agent_execution.agent_execution_util_schema import _ExecutionMessage


def _validate_message(message: object) -> _ExecutionMessage | None:
    try:
        return _ExecutionMessage.model_validate(message)
    except ValidationError:
        return None


def message_text(message: object) -> str:
    """Extract text from both AG-UI strings and TanStack text-part content."""
    parsed = _validate_message(message)
    if parsed is None:
        return ""
    content = parsed.content
    if isinstance(content, str):
        return content.strip()
    return "".join(part.text for part in content).strip()


def newest_user_message(input_data: RunAgentInput) -> tuple[str, str | None] | None:
    """Return the newest nonblank user text and its client message ID."""
    for message in reversed(input_data.messages):
        parsed = _validate_message(message)
        if parsed is None or parsed.role != "user":
            continue
        content = parsed.content
        text = (
            content.strip()
            if isinstance(content, str)
            else "".join(part.text for part in content).strip()
        )
        if text:
            message_id = parsed.id
            return text, str(message_id) if message_id is not None else None
    return None
