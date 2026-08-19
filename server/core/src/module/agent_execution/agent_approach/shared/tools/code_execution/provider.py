from typing import Literal, Protocol

from agents.tool import Tool
from pydantic import BaseModel, ConfigDict


class CodeExecutionSnapshot(BaseModel):
    """Provider-neutral view of a completed (or observed) execution call."""

    model_config = ConfigDict(frozen=True)

    call_id: str
    tool_name: str
    status: str | None = None
    code: str | None = None
    output: str | None = None


class CodeExecutionUpdate(BaseModel):
    """A normalized stream update consumed by the AG-UI adapter."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text_delta", "call_started", "code_delta", "snapshot", "tool_output"]
    delta: str | None = None
    snapshot: CodeExecutionSnapshot | None = None
    call_id: str | None = None
    tool_name: str | None = None
    output: str | None = None


class CodeExecutionProvider(Protocol):
    """Application boundary for hosted (or future MCP/WASI/OCI) execution."""

    def tool(self) -> Tool: ...

    def normalize_raw_event(self, event: object) -> CodeExecutionUpdate | None: ...

    def normalize_run_item_event(self, event: object) -> CodeExecutionUpdate | None: ...
