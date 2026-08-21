from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.encoders import jsonable_encoder
from pydantic import StringConstraints, ValidationError

from src.module.dataset_conversations.dataset_conversations_constants import (
    DATASET_CONVERSATION_MAX_LIMIT,
)
from src.module.dataset_conversations.dataset_conversations_router_schema import (
    DatasetConversationResponse,
)
from src.module.dataset_conversations.dataset_conversations_service import (
    DatasetConversationService,
)
from src.module.dataset_conversations.dataset_conversations_service_schema import (
    DatasetConversationServiceGetParams,
    DatasetConversationServiceListParams,
)

router = APIRouter(prefix="/dataset-conversations", tags=["dataset-conversations"])


@router.get(
    "",
    response_model=list[DatasetConversationResponse],
    summary="List dataset conversations",
    description="Return dataset conversations ordered by their database identifier.",
)
@inject
async def list_dataset_conversations(
    service: FromDishka[DatasetConversationService],
    offset: Annotated[int, Query(ge=0, description="Number of dataset conversations to skip")] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=DATASET_CONVERSATION_MAX_LIMIT, description="Maximum results to return"),
    ] = 20,
    tags: Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=100)]] | None,
        Query(max_length=50, description="Chat session tags (OR filtered)"),
    ] = None,
) -> list[DatasetConversationResponse]:
    try:
        params = DatasetConversationServiceListParams(offset=offset, limit=limit, tags=tags or [])
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=jsonable_encoder(error.errors())) from error
    dataset_conversations = await service.list(params)
    return [DatasetConversationResponse.model_validate(item) for item in dataset_conversations]


@router.get(
    "/{dataset_conversation_id}",
    response_model=DatasetConversationResponse,
    summary="Get a dataset conversation",
    description="Return a dataset conversation by its database identifier.",
)
@inject
async def get_dataset_conversation(
    dataset_conversation_id: Annotated[
        int, Path(gt=0, description="Dataset conversation database identifier")
    ],
    service: FromDishka[DatasetConversationService],
) -> DatasetConversationResponse:
    dataset_conversation = await service.get(
        DatasetConversationServiceGetParams(dataset_conversation_id=dataset_conversation_id)
    )
    if dataset_conversation is None:
        raise HTTPException(status_code=404, detail="Dataset conversation not found")
    return DatasetConversationResponse.model_validate(dataset_conversation)
