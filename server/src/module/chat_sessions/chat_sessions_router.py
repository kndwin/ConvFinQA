from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Annotated, cast

from ag_ui.core import BaseEvent, RunAgentInput, RunErrorEvent
from ag_ui.encoder import EventEncoder
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Path, Request, status
from fastapi.responses import StreamingResponse

from src.module.chat_sessions.agent.calculator_mini_chat_agent import CalculatorMiniChatAgent
from src.module.chat_sessions.agent.direct_mini_chat_agent import DirectMiniChatAgent
from src.module.chat_sessions.chat_sessions_constants import AgentVariant
from src.module.chat_sessions.chat_sessions_router_schema import (
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from src.module.chat_sessions.chat_sessions_service import ChatSessionService
from src.module.chat_sessions.chat_sessions_service_schema import (
    ChatSessionServiceCreateParams,
    ChatSessionServiceDeleteParams,
    ChatSessionServiceGetParams,
    ChatSessionServiceListParams,
    ChatSessionServiceUpdateParams,
)

router = APIRouter(tags=["chat-sessions"])


@router.get(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions",
    response_model=list[ChatSessionResponse],
    summary="List chat sessions",
    description="Return chat sessions newest first for a dataset conversation.",
)
@inject
async def list_chat_sessions(
    dataset_conversation_id: Annotated[
        int, Path(gt=0, description="Dataset conversation database identifier")
    ],
    service: FromDishka[ChatSessionService],
) -> list[ChatSessionResponse]:
    sessions = await service.list(
        ChatSessionServiceListParams(dataset_conversation_id=dataset_conversation_id)
    )
    return [ChatSessionResponse.model_validate(session) for session in sessions]


@router.post(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chat session",
    description="Create and persist an empty chat session for a dataset conversation.",
)
@inject
async def create_chat_session(
    dataset_conversation_id: Annotated[
        int, Path(gt=0, description="Dataset conversation database identifier")
    ],
    service: FromDishka[ChatSessionService],
    payload: ChatSessionCreateRequest | None = None,
) -> ChatSessionResponse:
    session = await service.create(
        ChatSessionServiceCreateParams(
            dataset_conversation_id=dataset_conversation_id,
            agent_variant=(payload or ChatSessionCreateRequest()).agent_variant,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Dataset conversation not found")
    return ChatSessionResponse.model_validate(session)


@router.get(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}/messages",
    response_model=list[ChatMessageResponse],
)
@inject
async def list_messages(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    chat_session_id: Annotated[int, Path(gt=0)],
    service: FromDishka[ChatSessionService],
) -> list[ChatMessageResponse]:
    messages = await service.messages(
        ChatSessionServiceGetParams(
            dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
        )
    )
    if messages is None:
        raise HTTPException(404, "Chat session not found")
    return [ChatMessageResponse.model_validate(message) for message in messages]


@router.get(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}",
    response_model=ChatSessionResponse,
)
@inject
async def get_chat_session(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    chat_session_id: Annotated[int, Path(gt=0)],
    service: FromDishka[ChatSessionService],
) -> ChatSessionResponse:
    session = await service.get(
        ChatSessionServiceGetParams(
            dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
        )
    )
    if session is None:
        raise HTTPException(404, "Chat session not found")
    return ChatSessionResponse.model_validate(session)


@router.patch(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}",
    response_model=ChatSessionResponse,
)
@inject
async def update_chat_session(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    chat_session_id: Annotated[int, Path(gt=0)],
    payload: ChatSessionUpdateRequest,
    service: FromDishka[ChatSessionService],
) -> ChatSessionResponse:
    session = await service.update(
        ChatSessionServiceUpdateParams(
            dataset_conversation_id=dataset_conversation_id,
            chat_session_id=chat_session_id,
            title=payload.title,
        )
    )
    if session is None:
        raise HTTPException(404, "Chat session not found")
    return ChatSessionResponse.model_validate(session)


@router.delete(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def delete_chat_session(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    chat_session_id: Annotated[int, Path(gt=0)],
    service: FromDishka[ChatSessionService],
) -> None:
    if not await service.delete(
        ChatSessionServiceDeleteParams(
            dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
        )
    ):
        raise HTTPException(404, "Chat session not found")


@router.post(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}/runs",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
@inject
async def run_agent(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    chat_session_id: Annotated[int, Path(gt=0)],
    input_data: RunAgentInput,
    service: FromDishka[ChatSessionService],
    direct_agent: FromDishka[DirectMiniChatAgent],
    calculator_agent: FromDishka[CalculatorMiniChatAgent],
    request: Request,
) -> StreamingResponse:
    encoder = EventEncoder(request.headers.get("accept") or "text/event-stream")

    async def encoded_events():
        try:
            session = await service.get(
                ChatSessionServiceGetParams(
                    dataset_conversation_id=dataset_conversation_id,
                    chat_session_id=chat_session_id,
                )
            )
            if session is None:
                events = _one(RunErrorEvent(message="Chat session not found", code="not_found"))
            elif session.agent_variant == AgentVariant.DIRECT_MINI:
                events = cast(
                    AsyncGenerator[BaseEvent],
                    direct_agent.run(dataset_conversation_id, chat_session_id, input_data),
                )
            elif session.agent_variant == AgentVariant.CALCULATOR_MINI:
                events = cast(
                    AsyncGenerator[BaseEvent],
                    calculator_agent.run(dataset_conversation_id, chat_session_id, input_data),
                )
            else:
                events = _one(RunErrorEvent(message="Unsupported agent variant", code="run_error"))
        except Exception:
            events = _one(
                RunErrorEvent(message="The assistant could not complete this run", code="run_error")
            )
        async with aclosing(events):
            async for event in events:
                yield encoder.encode(event)

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _one(event: BaseEvent) -> AsyncGenerator[BaseEvent]:
    yield event
