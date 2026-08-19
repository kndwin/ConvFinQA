from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Path, Query

from src.module.dataset_conversations.dataset_conversations_constants import (
    DATASET_CONVERSATION_MAX_LIMIT,
)
from src.module.dataset_conversations.dataset_conversations_router_schema import (
    DatasetConversationResponse,
    candidate_qa_from_dialogue_json,
)
from src.module.dataset_conversations.dataset_conversations_service import (
    DatasetConversationService,
)
from src.module.dataset_conversations.dataset_conversations_service_schema import (
    DatasetConversationServiceGetParams,
    DatasetConversationServiceListParams,
)

router = APIRouter(prefix="/dataset-conversations", tags=["dataset-conversations"])


def _response(item: object) -> DatasetConversationResponse:
    dialogue_json = getattr(item, "dialogue_json", "")
    values = {
        field: getattr(item, field)
        for field in DatasetConversationResponse.model_fields
        if field != "candidate_qa"
    }
    values["candidate_qa"] = candidate_qa_from_dialogue_json(dialogue_json)
    return DatasetConversationResponse.model_validate(values)


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
) -> list[DatasetConversationResponse]:
    dataset_conversations = await service.list(
        DatasetConversationServiceListParams(offset=offset, limit=limit)
    )
    return [_response(item) for item in dataset_conversations]


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
    return _response(dataset_conversation)
