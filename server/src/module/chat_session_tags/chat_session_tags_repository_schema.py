from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.module.chat_session_tags.chat_session_tags_constants import (
    CHAT_SESSION_TAG_MAX_LIMIT,
    CHAT_SESSION_TAG_MAX_VALUE_LENGTH,
)


class ChatSessionTagValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=CHAT_SESSION_TAG_MAX_VALUE_LENGTH)

    @field_validator("value")
    @classmethod
    def trim_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("tag value must not be blank")
        return value


class ChatSessionTagRepositoryGetParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    chat_session_tag_id: Annotated[int, Field(strict=True, gt=0)]


class ChatSessionTagRepositoryListParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    offset: Annotated[int, Field(strict=True, ge=0)] = 0
    limit: Annotated[int, Field(strict=True, ge=1, le=CHAT_SESSION_TAG_MAX_LIMIT)] = 20


class ChatSessionTagRepositoryCreateParams(ChatSessionTagValue):
    pass


class ChatSessionTagRepositoryUpdateParams(ChatSessionTagRepositoryGetParams):
    value: str = Field(min_length=1, max_length=CHAT_SESSION_TAG_MAX_VALUE_LENGTH)

    @field_validator("value")
    @classmethod
    def trim_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("tag value must not be blank")
        return value
