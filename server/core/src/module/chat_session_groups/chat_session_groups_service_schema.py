from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.chat_session_groups.chat_session_groups_repository_schema import (
    ChatSessionGroupRepositoryDeleteParams,
    ChatSessionGroupRepositoryGetByIdParams,
    ChatSessionGroupRepositoryGetParams,
    ChatSessionGroupRepositoryListParams,
    ChatSessionGroupRepositoryUpdateParams,
)


class ChatSessionGroupConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_approach: AgentApproach
    model: OpenAIModel
    tags: list[dict[str, str]] = Field(default_factory=list)
    ensemble_candidates: list[AgentApproach] | None = Field(
        default=None, min_length=2, max_length=3
    )


class ChatSessionGroupServiceListParams(ChatSessionGroupRepositoryListParams):
    pass


class ChatSessionGroupServiceGetParams(ChatSessionGroupRepositoryGetParams):
    pass


class ChatSessionGroupServiceGetByIdParams(ChatSessionGroupRepositoryGetByIdParams):
    pass


class ChatSessionGroupServiceUpdateParams(ChatSessionGroupRepositoryUpdateParams):
    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class ChatSessionGroupServiceDeleteParams(ChatSessionGroupRepositoryDeleteParams):
    pass


class ChatSessionGroupServiceCreateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_conversation_id: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=200)
    configs: list[ChatSessionGroupConfig] = Field(min_length=2, max_length=4)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value
