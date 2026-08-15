from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.module.chat_sessions.chat_sessions_constants import AgentVariant


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_conversation_id: int
    agent_variant: AgentVariant
    created_at: datetime
    title: str | None = None
    updated_at: datetime


class ChatSessionCreateRequest(BaseModel):
    agent_variant: AgentVariant = AgentVariant.DIRECT_MINI


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    chat_session_id: int
    role: str
    content: str
    created_at: datetime


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = Field(max_length=60)
