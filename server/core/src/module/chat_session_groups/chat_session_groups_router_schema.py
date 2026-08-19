from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.chat_sessions.chat_sessions_router_schema import (
    ChatSessionResponse,
    ChatSessionTagInput,
)


class ChatSessionGroupConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_approach: AgentApproach
    model: OpenAIModel
    tags: list[ChatSessionTagInput] = Field(default_factory=list, max_length=50)
    ensemble_candidates: list[AgentApproach] | None = Field(
        default=None, min_length=2, max_length=3
    )


class ChatSessionGroupCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    sessions: list[ChatSessionGroupConfig] = Field(min_length=2, max_length=4)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class ChatSessionGroupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(max_length=200)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("title must not be blank")
        return value


class ChatSessionGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dataset_conversation_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    sessions: list[ChatSessionResponse] = Field(default_factory=list)
