import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from src.main import create_app
from src.module.chat_session_groups.chat_session_groups_router import create_group
from src.module.chat_session_groups.chat_session_groups_router_schema import (
    ChatSessionGroupCreateRequest,
)
from src.module.chat_session_groups.chat_session_groups_service_schema import (
    ChatSessionGroupConfig,
    ChatSessionGroupServiceCreateParams,
)


def config(i: int = 0) -> dict[str, object]:
    return {
        "agent_approach": "baseline" if i % 2 == 0 else "baseline-tool",
        "model": "gpt-5.6-luna",
        "tags": [],
    }


def test_group_requires_two_to_four_typed_configs() -> None:
    with pytest.raises(ValidationError):
        ChatSessionGroupCreateRequest(sessions=[config()])
    payload = ChatSessionGroupCreateRequest(sessions=[config(), config(1)])
    service = ChatSessionGroupServiceCreateParams(
        dataset_conversation_id=1,
        title=payload.title,
        configs=[
            ChatSessionGroupConfig.model_validate(item.model_dump()) for item in payload.sessions
        ],
    )
    assert len(service.configs) == 2


def test_title_is_trimmed_and_blank_rejected() -> None:
    assert (
        ChatSessionGroupCreateRequest(title="  hello  ", sessions=[config(), config()]).title
        == "hello"
    )
    with pytest.raises(ValidationError):
        ChatSessionGroupCreateRequest(title=" ", sessions=[config(), config()])


@pytest.mark.asyncio
async def test_create_router_converts_ordered_configs_and_tags() -> None:
    captured = None

    class FakeService:
        async def create(self, params):
            nonlocal captured
            captured = params
            return None

    with pytest.raises(HTTPException) as error:
        await create_group.__dishka_orig_func__(
            7,
            ChatSessionGroupCreateRequest(
                sessions=[
                    {**config(), "tags": [{"value": "first"}]},
                    {**config(1), "tags": [{"value": "second"}]},
                ]
            ),
            FakeService(),
        )
    assert error.value.status_code == 404
    assert captured is not None
    assert [(item.agent_approach, item.model, item.tags) for item in captured.configs] == [
        ("baseline", "gpt-5.6-luna", [{"value": "first"}]),
        ("baseline-tool", "gpt-5.6-luna", [{"value": "second"}]),
    ]


def test_group_openapi_has_all_routes_and_schemas() -> None:
    schema = create_app().openapi()
    assert set(schema["paths"]) >= {
        "/dataset-conversations/{dataset_conversation_id}/chat-session-groups",
        "/chat-session-groups/{chat_session_group_id}",
    }
    assert {"get", "post"} <= set(
        schema["paths"]["/dataset-conversations/{dataset_conversation_id}/chat-session-groups"]
    )
    assert {"get", "patch", "delete"} <= set(
        schema["paths"]["/chat-session-groups/{chat_session_group_id}"]
    )
    assert {
        "ChatSessionGroupConfig",
        "ChatSessionGroupCreateRequest",
        "ChatSessionGroupUpdateRequest",
        "ChatSessionGroupResponse",
    } <= set(schema["components"]["schemas"])
