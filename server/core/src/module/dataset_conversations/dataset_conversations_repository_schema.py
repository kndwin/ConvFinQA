from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

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
