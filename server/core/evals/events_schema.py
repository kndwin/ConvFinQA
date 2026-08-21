from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str | None = None
    arguments: str = ""
    result: str | None = None


class ModelUsageObservation(BaseModel):
    """Usage reported by the application for one or more real model requests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)


class TextEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_CHUNK"]
    text: str = Field(validation_alias=AliasChoices("delta", "content", "text"))


class RunErrorEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["RUN_ERROR"]
    message: str = Field(validation_alias=AliasChoices("message", "error"))


class ModelUsagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    calls: tuple[ModelUsageObservation, ...]

    @model_validator(mode="before")
    @classmethod
    def normalize_single_call(cls, value: Any) -> Any:
        if isinstance(value, dict) and "calls" not in value:
            return {"calls": (value,)}
        return value


class ModelUsageEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["CUSTOM"]
    name: Literal["model_usage"]
    value: ModelUsagePayload


class ToolEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal[
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "TOOL_CALL_CHUNK",
        "TOOL_CALL_RESULT",
    ]
    call_id: str = Field(
        default="unknown",
        validation_alias=AliasChoices("tool_call_id", "toolCallId", "id"),
    )
    name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("tool_call_name", "toolCallName", "name"),
    )
    arguments: str | None = Field(
        default=None,
        validation_alias=AliasChoices("delta", "args", "arguments"),
    )
    result: str | None = Field(
        default=None,
        validation_alias=AliasChoices("content", "result"),
    )


class IgnoredEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str = ""


class PendingToolCall(BaseModel):
    id: str
    name: str | None = None
    arguments: str = ""
    result: str | None = None


ExecutionEvent = TextEvent | RunErrorEvent | ModelUsageEvent | ToolEvent | IgnoredEvent
