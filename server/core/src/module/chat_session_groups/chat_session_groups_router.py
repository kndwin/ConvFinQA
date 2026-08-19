from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Path, Query, status

from src.module.chat_session_groups.chat_session_groups_router_schema import (
    ChatSessionGroupCreateRequest,
    ChatSessionGroupResponse,
    ChatSessionGroupUpdateRequest,
)
from src.module.chat_session_groups.chat_session_groups_service import ChatSessionGroupService
from src.module.chat_session_groups.chat_session_groups_service_schema import (
    ChatSessionGroupConfig as ServiceChatSessionGroupConfig,
)
from src.module.chat_session_groups.chat_session_groups_service_schema import (
    ChatSessionGroupServiceCreateParams,
    ChatSessionGroupServiceDeleteParams,
    ChatSessionGroupServiceGetByIdParams,
    ChatSessionGroupServiceListParams,
    ChatSessionGroupServiceUpdateParams,
)

router = APIRouter(tags=["chat-session-groups"])


def response(detail) -> ChatSessionGroupResponse:
    group, sessions = detail
    return ChatSessionGroupResponse.model_validate(
        {
            "id": group.id,
            "dataset_conversation_id": group.dataset_conversation_id,
            "title": group.title,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "sessions": sessions,
        }
    )


@router.get(
    "/dataset-conversations/{dataset_conversation_id}/chat-session-groups",
    response_model=list[ChatSessionGroupResponse],
)
@inject
async def list_groups(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    service: FromDishka[ChatSessionGroupService],
):
    return [
        response(item)
        for item in await service.list(
            ChatSessionGroupServiceListParams(dataset_conversation_id=dataset_conversation_id)
        )
    ]


@router.post(
    "/dataset-conversations/{dataset_conversation_id}/chat-session-groups",
    response_model=ChatSessionGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_group(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    payload: ChatSessionGroupCreateRequest,
    service: FromDishka[ChatSessionGroupService],
):
    # The FK provides the final consistency check; a missing parent is reported distinctly.
    try:
        detail = await service.create(
            ChatSessionGroupServiceCreateParams(
                dataset_conversation_id=dataset_conversation_id,
                title=payload.title,
                configs=[
                    ServiceChatSessionGroupConfig.model_validate(config.model_dump())
                    for config in payload.sessions
                ],
            )
        )
    except Exception as exc:
        if "foreign key" in str(exc).lower():
            raise HTTPException(404, "Dataset conversation not found") from exc
        raise
    if detail is None:
        raise HTTPException(404, "Dataset conversation not found")
    return response(detail)


@router.get("/chat-session-groups/{chat_session_group_id}", response_model=ChatSessionGroupResponse)
@inject
async def get_group(
    chat_session_group_id: Annotated[int, Path(gt=0)], service: FromDishka[ChatSessionGroupService]
):
    detail = await service.get_by_id(
        ChatSessionGroupServiceGetByIdParams(chat_session_group_id=chat_session_group_id)
    )
    if detail is None:
        raise HTTPException(404, "Chat session group not found")
    return response(detail)


@router.patch(
    "/chat-session-groups/{chat_session_group_id}", response_model=ChatSessionGroupResponse
)
@inject
async def update_group(
    chat_session_group_id: Annotated[int, Path(gt=0)],
    payload: ChatSessionGroupUpdateRequest,
    service: FromDishka[ChatSessionGroupService],
):
    detail = await service.get_by_id(
        ChatSessionGroupServiceGetByIdParams(chat_session_group_id=chat_session_group_id)
    )
    if detail is None:
        raise HTTPException(404, "Chat session group not found")
    detail = await service.update(
        ChatSessionGroupServiceUpdateParams(
            chat_session_group_id=chat_session_group_id,
            dataset_conversation_id=detail[0].dataset_conversation_id,
            title=payload.title,
        )
    )
    return response(detail)


@router.delete(
    "/chat-session-groups/{chat_session_group_id}", status_code=status.HTTP_204_NO_CONTENT
)
@inject
async def delete_group(
    chat_session_group_id: Annotated[int, Path(gt=0)],
    service: FromDishka[ChatSessionGroupService],
    delete_chat_sessions: bool = Query(
        False, description="Also delete child sessions; defaults to preserving them."
    ),
):
    detail = await service.get_by_id(
        ChatSessionGroupServiceGetByIdParams(chat_session_group_id=chat_session_group_id)
    )
    if detail is None:
        raise HTTPException(404, "Chat session group not found")
    await service.delete(
        ChatSessionGroupServiceDeleteParams(
            chat_session_group_id=chat_session_group_id,
            dataset_conversation_id=detail[0].dataset_conversation_id,
            delete_chat_sessions=delete_chat_sessions,
        )
    )
