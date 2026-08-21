from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evals.events_schema import ModelUsageObservation, ToolCall


class ObservedTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn: int = Field(gt=0)
    question: str
    expected: str | None
    executed_answer: str | None = None
    turn_program: str | None = None
    qa_split: bool | None = None
    actual: str
    latency_seconds: float = Field(ge=0)
    run_id: str
    thread_id: str
    session_id: str | None = None
    tools: tuple[ToolCall, ...] = ()
    model_usage: tuple[ModelUsageObservation, ...] = ()
    # Target-aware structured processing is performed before scoring.  Keeping the
    # artifact on the observation prevents scorers from reinterpreting raw output.
    structured: dict[str, Any] | None = None
