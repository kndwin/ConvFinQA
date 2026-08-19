from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.exc import IntegrityError

from src.module.chat_session_tags.chat_session_tags_constants import CHAT_SESSION_TAG_MAX_LIMIT
from src.module.chat_session_tags.chat_session_tags_router_schema import (
    ChatSessionTagRequest,
    ChatSessionTagResponse,
)
from src.module.chat_session_tags.chat_session_tags_service import ChatSessionTagService
from src.module.chat_session_tags.chat_session_tags_service_schema import (
    ChatSessionTagServiceCreateParams,
    ChatSessionTagServiceGetParams,
    ChatSessionTagServiceListParams,
    ChatSessionTagServiceUpdateParams,
)

router = APIRouter(prefix="/chat-session-tags", tags=["chat-session-tags"])


def _conflict() -> HTTPException:
    return HTTPException(status_code=409, detail="Chat session tag value already exists")


@router.get("", response_model=list[ChatSessionTagResponse], summary="List chat session tags")
@inject
async def list_chat_session_tags(
    service: FromDishka[ChatSessionTagService],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=CHAT_SESSION_TAG_MAX_LIMIT)] = 20,
) -> list[ChatSessionTagResponse]:
    tags = await service.list(ChatSessionTagServiceListParams(offset=offset, limit=limit))
    return [ChatSessionTagResponse.model_validate(tag) for tag in tags]


@router.post("", response_model=ChatSessionTagResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_chat_session_tag(
    payload: ChatSessionTagRequest, service: FromDishka[ChatSessionTagService]
) -> ChatSessionTagResponse:
    try:
        tag = await service.create(ChatSessionTagServiceCreateParams(value=payload.value))
    except IntegrityError:
        raise _conflict() from None
    return ChatSessionTagResponse.model_validate(tag)


@router.get("/{chat_session_tag_id}", response_model=ChatSessionTagResponse)
@inject
async def get_chat_session_tag(
    chat_session_tag_id: Annotated[int, Path(gt=0)], service: FromDishka[ChatSessionTagService]
) -> ChatSessionTagResponse:
    tag = await service.get(ChatSessionTagServiceGetParams(chat_session_tag_id=chat_session_tag_id))
    if tag is None:
        raise HTTPException(404, "Chat session tag not found")
    return ChatSessionTagResponse.model_validate(tag)


@router.patch("/{chat_session_tag_id}", response_model=ChatSessionTagResponse)
@inject
async def update_chat_session_tag(
    chat_session_tag_id: Annotated[int, Path(gt=0)],
    payload: ChatSessionTagRequest,
    service: FromDishka[ChatSessionTagService],
) -> ChatSessionTagResponse:
    try:
        tag = await service.update(
            ChatSessionTagServiceUpdateParams(
                chat_session_tag_id=chat_session_tag_id, value=payload.value
            )
        )
    except IntegrityError:
        raise _conflict() from None
    if tag is None:
        raise HTTPException(404, "Chat session tag not found")
    return ChatSessionTagResponse.model_validate(tag)


@router.delete("/{chat_session_tag_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_chat_session_tag(
    chat_session_tag_id: Annotated[int, Path(gt=0)], service: FromDishka[ChatSessionTagService]
) -> None:
    if not await service.delete(
        ChatSessionTagServiceGetParams(chat_session_tag_id=chat_session_tag_id)
    ):
        raise HTTPException(404, "Chat session tag not found")
