from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.module.dataset_conversations.dataset_conversations_constants import (
    DATASET_CONVERSATION_MAX_LIMIT,
)


class DatasetConversationRepositoryGetParams(BaseModel):
    """Validated parameters for retrieving a dataset conversation."""

    model_config = ConfigDict(extra="forbid", validate_default=True)

    dataset_conversation_id: Annotated[int, Field(strict=True, gt=0)]


class DatasetConversationRepositoryListParams(BaseModel):
    """Validated pagination parameters for listing dataset conversations."""

    model_config = ConfigDict(extra="forbid", validate_default=True)

    offset: Annotated[int, Field(strict=True, ge=0)] = 0
    limit: Annotated[int, Field(strict=True, ge=1, le=DATASET_CONVERSATION_MAX_LIMIT)] = 20
    tags: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("tags must be a list")
        normalized: list[str] = []
        for tag in value:
            if not isinstance(tag, str):
                raise ValueError("tags must be strings")
            item = tag.strip()
            if not item or len(item) > 100:
                raise ValueError("tags must be nonblank and at most 100 characters")
            if item in normalized:
                raise ValueError("tags must not contain duplicates")
            normalized.append(item)
        return normalized
