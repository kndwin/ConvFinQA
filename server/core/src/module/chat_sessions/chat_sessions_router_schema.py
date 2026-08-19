import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.module.agent_execution.agent_approach.ensemble.definition import EnsembleConfig
from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel


class ChatSessionTagInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=100)

    @field_validator("value")
    @classmethod
    def trim_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("tag value must not be blank")
        return value


class ChatSessionTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    value: str


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_conversation_id: int
    agent_approach: AgentApproach
    prompt_version: str
    context_version: str
    model: OpenAIModel
    ensemble_config_json: EnsembleConfig | None = None
    created_at: datetime
    title: str | None = None
    updated_at: datetime
    tags: list[ChatSessionTagResponse] = Field(default_factory=list)

    @field_validator("ensemble_config_json", mode="before")
    @classmethod
    def parse_ensemble_config(cls, value: object) -> object:
        if isinstance(value, str):
            return json.loads(value)
        return value


class ChatSessionCreateRequest(BaseModel):
    agent_approach: AgentApproach = AgentApproach.BASELINE
    model: OpenAIModel = OpenAIModel.GPT_5_6_LUNA
    tags: list[ChatSessionTagInput] = Field(default_factory=list, max_length=50)
    ensemble_candidates: list[AgentApproach] | None = Field(
        default=None, min_length=2, max_length=3
    )

    @model_validator(mode="after")
    def validate_ensemble(self) -> ChatSessionCreateRequest:
        if self.agent_approach is AgentApproach.ENSEMBLE:
            candidates = self.ensemble_candidates or [
                AgentApproach.BASELINE,
                AgentApproach.BASELINE_TOOL,
                AgentApproach.PROGRAM_OF_THOUGHT,
            ]
            if any(candidate is AgentApproach.ENSEMBLE for candidate in candidates) or len(
                set(candidates)
            ) != len(candidates):
                raise ValueError("ensemble candidates must be unique non-ensemble approaches")
            self.ensemble_candidates = candidates
        elif self.ensemble_candidates is not None:
            raise ValueError("ensemble_candidates is only valid for ensemble sessions")
        return self

    @field_validator("tags")
    @classmethod
    def reject_duplicate_tags(cls, tags: list[ChatSessionTagInput]) -> list[ChatSessionTagInput]:
        values = [tag.value for tag in tags]
        if len(values) != len(set(values)):
            raise ValueError("tag values must be unique")
        return tags


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    chat_session_id: int
    role: str
    content: str
    created_at: datetime


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = Field(max_length=60)
