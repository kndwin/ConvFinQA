import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Annotated, cast

from ag_ui.core import BaseEvent, RunAgentInput, RunErrorEvent
from ag_ui.encoder import EventEncoder
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Path, Request, status
from fastapi.responses import StreamingResponse

from src.module.agent_execution.execution.durable.durable_execution_backend import (
    TemporalUnavailableError,
)
from src.module.chat_sessions.chat_session_run_adapter import (
    ChatSessionRunAdapter,
)
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
from src.module.chat_sessions.run_execution_coordinator import RunExecutionCoordinator

router = APIRouter(tags=["chat-sessions"])


def _encode_event(encoder: EventEncoder, event: BaseEvent) -> str:
    """Encode AG-UI while exposing a safe Workflow Stream cursor as SSE id."""
    encoded = encoder.encode(event)
    cursor = getattr(event, "cursor", None)
    return f"id: {cursor}\n{encoded}" if isinstance(cursor, str) and cursor else encoded


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
    selection = payload or ChatSessionCreateRequest()
    session = await service.create(
        ChatSessionServiceCreateParams(
            dataset_conversation_id=dataset_conversation_id,
            agent_approach=selection.agent_approach,
            model=selection.model,
            tags=[{"value": tag.value} for tag in selection.tags],
            ensemble_candidates=selection.ensemble_candidates,
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
    request: Request,
    coordinator: FromDishka[RunExecutionCoordinator],
) -> StreamingResponse:
    encoder = EventEncoder(request.headers.get("accept") or "text/event-stream")
    try:
        # Do this before constructing the response so disabled Temporal remains
        # an HTTP 503 rather than an error hidden inside a 200 SSE body.
        plan = await coordinator.prepare(dataset_conversation_id, chat_session_id, input_data)
    except TemporalUnavailableError as error:
        raise HTTPException(503, "Temporal is unavailable") from error
    except LookupError as error:
        raise HTTPException(404, "Chat session not found") from error

    async def encoded_events():
        events = cast(
            AsyncGenerator[BaseEvent],
            coordinator.stream(plan, dataset_conversation_id, chat_session_id, input_data),
        )
        try:
            async with aclosing(events):
                async for event in events:
                    yield _encode_event(encoder, event)
        except Exception:
            yield _encode_event(
                encoder,
                RunErrorEvent(
                    message="The assistant could not complete this run", code="run_error"
                ),
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}/runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
@inject
async def run_events(
    dataset_conversation_id: Annotated[int, Path(gt=0)],
    chat_session_id: Annotated[int, Path(gt=0)],
    run_id: str,
    request: Request,
    service: FromDishka[ChatSessionService],
    run_adapter: FromDishka[ChatSessionRunAdapter],
) -> StreamingResponse:
    session = await service.get(
        ChatSessionServiceGetParams(
            dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
        )
    )
    run = await run_adapter.get_run(chat_session_id, run_id) if session else None
    if session is None or run is None or not run.temporal_workflow_id:
        raise HTTPException(404, "Run not found")
    try:
        await run_adapter.preflight()  # preflight before returning a 200 stream
        candidates = await run_adapter.candidate_names(dataset_conversation_id, chat_session_id)
    except TemporalUnavailableError as error:
        raise HTTPException(503, "Temporal is unavailable") from error
    sources = {f"candidate:{name}" for name in candidates} | {"reviewer"}
    cursor = run_adapter.decode_cursor(request.headers.get("last-event-id"), sources)
    encoder = EventEncoder(request.headers.get("accept") or "text/event-stream")

    async def encoded_events():
        assert run.temporal_workflow_id is not None
        async for event in run_adapter.stream_events(
            run.temporal_workflow_id, f"chat:{chat_session_id}", run_id, candidates, cursor
        ):
            yield _encode_event(encoder, event)

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}/runs/{run_id}"
)
@inject
async def describe_run(
    dataset_conversation_id: int,
    chat_session_id: int,
    run_id: str,
    service: FromDishka[ChatSessionService],
    run_adapter: FromDishka[ChatSessionRunAdapter],
):
    if (
        await service.get(
            ChatSessionServiceGetParams(
                dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Run not found")
    run = await run_adapter.get_run(chat_session_id, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    try:
        description = await (
            await run_adapter.handle(
                run.temporal_workflow_id or f"ensemble:{chat_session_id}:{run_id}"
            )
        ).describe()
        temporal_status = str(getattr(description, "status", "unknown"))
    except TemporalUnavailableError as error:
        raise HTTPException(503, "Temporal is unavailable") from error
    return {
        "run_id": run.run_id,
        "status": run.status,
        "temporal_status": temporal_status,
        "workflow_id": run.temporal_workflow_id,
        "diagnostics": json.loads(run.diagnostics_json) if run.diagnostics_json else None,
        "error": run.error,
    }


@router.get(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}/runs/{run_id}/result"
)
@inject
async def run_result(
    dataset_conversation_id: int,
    chat_session_id: int,
    run_id: str,
    service: FromDishka[ChatSessionService],
    run_adapter: FromDishka[ChatSessionRunAdapter],
):
    if (
        await service.get(
            ChatSessionServiceGetParams(
                dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Run not found")
    run = await run_adapter.get_run(chat_session_id, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    if run.status != "completed":
        raise HTTPException(409, "Run result is not ready")
    return {
        "run_id": run_id,
        "assistant_message_id": run.assistant_message_id,
        "diagnostics": json.loads(run.diagnostics_json) if run.diagnostics_json else None,
    }


@router.delete(
    "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}/runs/{run_id}",
    status_code=204,
)
@inject
async def cancel_run(
    dataset_conversation_id: int,
    chat_session_id: int,
    run_id: str,
    service: FromDishka[ChatSessionService],
    run_adapter: FromDishka[ChatSessionRunAdapter],
):
    if (
        await service.get(
            ChatSessionServiceGetParams(
                dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Run not found")
    run = await run_adapter.get_run(chat_session_id, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    try:
        await run_adapter.cancel(
            chat_session_id,
            run_id,
            run.temporal_workflow_id or f"ensemble:{chat_session_id}:{run_id}",
        )
    except TemporalUnavailableError as error:
        raise HTTPException(503, "Temporal is unavailable") from error
