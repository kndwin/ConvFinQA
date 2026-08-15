from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.module.chat_sessions.chat_sessions_constants import AgentVariant


class ChatSessionRepositoryListParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionRepositoryGetParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]
    chat_session_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionRepositoryCreateParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]
    agent_variant: AgentVariant = AgentVariant.DIRECT_MINI


class ChatSessionRepositoryUpdateParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]
    chat_session_id: Annotated[int, Field(strict=True, gt=0)]
    title: str | None = Field(max_length=60)


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
