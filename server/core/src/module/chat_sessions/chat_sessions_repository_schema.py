from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel


class ChatSessionRepositoryListParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]


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


class ChatSessionRepositoryGetParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]
    chat_session_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionRepositoryCreateParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]
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


class ChatSessionRepositoryUpdateParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]
    chat_session_id: Annotated[int, Field(strict=True, gt=0)]
    title: str | None = Field(default=None, max_length=60)
    title_provided: bool = True
    tags: list[ChatSessionTagInput] | None = Field(default=None, max_length=50)
    tags_provided: bool = False

class ChatSessionRepositoryDeleteParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]
    chat_session_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionRepositoryPersistUserMessageParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    chat_session_id: Annotated[int, Field(strict=True, gt=0)]
    content: str
    client_message_id: str | None = None


class ChatSessionRepositoryPersistAssistantMessageParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    chat_session_id: Annotated[int, Field(strict=True, gt=0)]
    content: str
