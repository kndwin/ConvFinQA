from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionGroupRepositoryListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionGroupRepositoryGetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chat_session_group_id: Annotated[int, Field(strict=True, gt=0)]
    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionGroupRepositoryGetByIdParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chat_session_group_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionGroupRepositoryUpdateParams(ChatSessionGroupRepositoryGetParams):
    title: str | None = Field(max_length=200)


class ChatSessionGroupRepositoryDeleteParams(ChatSessionGroupRepositoryGetParams):
    delete_chat_sessions: bool = False
