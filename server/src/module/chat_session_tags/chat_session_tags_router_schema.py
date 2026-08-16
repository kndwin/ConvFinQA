from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.module.chat_session_tags.chat_session_tags_constants import (
    CHAT_SESSION_TAG_MAX_VALUE_LENGTH,
)


class ChatSessionTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=CHAT_SESSION_TAG_MAX_VALUE_LENGTH)

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
