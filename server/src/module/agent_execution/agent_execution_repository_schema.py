"""Schemas for the agent execution repository transcript."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Role = Literal["user", "assistant"]


class ConversationMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    content: str
    message_id: str | None = None
