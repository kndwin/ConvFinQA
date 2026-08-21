from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    created_at: datetime
    title: str | None = None
    updated_at: datetime
    tags: list[ChatSessionTagResponse] = Field(default_factory=list)


class ChatSessionCreateRequest(BaseModel):
    agent_approach: AgentApproach = AgentApproach.BASELINE
    model: OpenAIModel = OpenAIModel.GPT_5_6_LUNA
    tags: list[ChatSessionTagInput] = Field(default_factory=list, max_length=50)

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
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=60)
    tags: list[ChatSessionTagInput] | None = Field(default=None, max_length=50)

    @field_validator("tags")
    @classmethod
    def reject_duplicate_tags(
        cls, tags: list[ChatSessionTagInput] | None
    ) -> list[ChatSessionTagInput] | None:
        if tags is None:
            return None
        values = [tag.value for tag in tags]
        if len(values) != len(set(values)):
            raise ValueError("tag values must be unique")
        return tags
