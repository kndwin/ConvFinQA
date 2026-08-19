from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_ids: tuple[int, ...] = Field(min_length=1)
    targets: tuple[str, ...] = Field(min_length=1)
    executor: Literal["direct", "remote"] = "direct"
    application_model: str = Field(default="gpt-5.6-luna", min_length=1)
    base_url: HttpUrl = HttpUrl("http://127.0.0.1:8000")
    keep_sessions: bool = False

    @field_validator("dataset_ids")
    @classmethod
    def positive_ids(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(item <= 0 for item in value):
            raise ValueError("dataset IDs must be positive")
        return value


class ExpectedTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=1)
    answer: str | None = None


class ConversationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: int = Field(gt=0)
    document: str
    turns: tuple[ExpectedTurn, ...] = Field(min_length=1)
    source_id: str | None = None


class TargetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    id: str
    approach: Any
    prompt: Any
    context_version: str
    context_hash: str

    def metadata(self, model: str) -> dict[str, str]:
        return {
            "target": self.id,
            "agent_approach": str(self.approach),
            "prompt_version": self.prompt.id,
            "prompt_hash": self.prompt.content_hash,
            "context_version": self.context_version,
            "context_hash": self.context_hash,
            "model": model,
        }


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


class ObservedTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn: int = Field(gt=0)
    question: str
    expected: str | None
    actual: str
    latency_seconds: float = Field(ge=0)
    run_id: str
    thread_id: str
    session_id: str | None = None
    tools: tuple[ToolCall, ...] = ()
    model_usage: tuple[ModelUsageObservation, ...] = ()
