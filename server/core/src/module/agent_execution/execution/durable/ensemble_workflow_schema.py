"""Workflow-safe ensemble payloads (no database or provider objects)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EnsembleCandidateInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    approach: str
    name: str
    instructions: str
    rendered_context: str
    model: str
    prompt_version: str
    prompt_hash: str
    context_version: str
    context_hash: str
    trace_metadata: dict[str, str] = Field(default_factory=dict)


class EnsembleFinalizationTarget(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    chat_session_id: int
    workflow_id: str


class EnsembleWorkflowInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    question: str
    context: str
    candidates: tuple[EnsembleCandidateInput, ...]
    reviewer_instructions: str
    reviewer_model: str
    trace_metadata: dict[str, str] = Field(default_factory=dict)
    finalization: EnsembleFinalizationTarget | None = None


class EnsembleCandidateOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    approach: str
    status: Literal["completed", "failed"]
    final_output: str = ""
    error: str = ""
    duration_ms: int = Field(default=0, ge=0)
    prompt_version: str = ""
    prompt_hash: str = ""
    context_version: str = ""
    context_hash: str = ""
    workflow_id: str = ""


class EnsembleWorkflowOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    reviewer_output: str
    candidates: tuple[EnsembleCandidateOutput, ...]
    reviewer_prompt_version: str = "ensemble-reviewer:v1"


class EnsembleFinalizationInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    target: EnsembleFinalizationTarget
    output: EnsembleWorkflowOutput


class EnsembleFailureFinalizationInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    target: EnsembleFinalizationTarget
    error: str = "ensemble reviewer failed"
