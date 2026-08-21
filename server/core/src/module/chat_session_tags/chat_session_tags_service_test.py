import asyncio
import builtins
import unittest
from typing import Any, cast

from pydantic import ValidationError

from src.module.chat_session_tags.chat_session_tags_repository import ChatSessionTagRepository
from src.module.chat_session_tags.chat_session_tags_repository_schema import (
    ChatSessionTagRepositoryCreateParams,
    ChatSessionTagRepositoryGetParams,
    ChatSessionTagRepositoryListParams,
    ChatSessionTagRepositoryUpdateParams,
)
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
from src.platform.database.models import (
    ChatSessionTable,
    ChatSessionTagTable,
)
from src.platform.observability import NOOP_OBSERVABILITY


def run(coro: Any) -> Any:
    return asyncio.run(coro)


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.tag = ChatSessionTagTable(id=7, value="one")

    async def list(self, params: Any) -> builtins.list[ChatSessionTagTable]:
        self.calls.append(("list", params))
        return [self.tag]

    async def get(self, params: Any) -> ChatSessionTagTable:
        self.calls.append(("get", params))
        return self.tag

    async def create(self, params: Any) -> ChatSessionTagTable:
        self.calls.append(("create", params))
        return self.tag

    async def update(self, params: Any) -> ChatSessionTagTable:
        self.calls.append(("update", params))
        return self.tag

    async def delete(self, params: Any) -> bool:
        self.calls.append(("delete", params))
        return True


class FakeSession:
    def __init__(self) -> None:
        self.items: dict[int, ChatSessionTagTable] = {1: ChatSessionTagTable(id=1, value="old")}
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.commits = 0
        self.refreshed = 0

    def add(self, item: Any) -> None:
        self.added.append(item)

    async def get(self, _model: Any, item_id: int) -> ChatSessionTagTable | None:
        return self.items.get(item_id)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _item: Any) -> None:
        self.refreshed += 1

    async def delete(self, item: Any) -> None:
        self.deleted.append(item)


class ChatSessionTagSchemaTests(unittest.TestCase):
    def test_request_trims_and_rejects_blank_and_invalid_lengths(self) -> None:
        self.assertEqual(ChatSessionTagRequest(value="  comparison/42 ").value, "comparison/42")
        for value in ("", "   ", "x" * 101):
            with self.subTest(value=repr(value)), self.assertRaises(ValidationError):
                ChatSessionTagRequest(value=value)

    def test_repository_value_and_pagination_validation(self) -> None:
        self.assertEqual(ChatSessionTagRepositoryCreateParams(value=" x ").value, "x")
        self.assertEqual(
            ChatSessionTagRepositoryListParams().model_dump(), {"offset": 0, "limit": 20}
        )
        invalid_pagination = cast(
            list[dict[str, Any]],
            ({"offset": -1}, {"limit": 0}, {"limit": 101}, {"offset": "1"}),
        )
        for kwargs in invalid_pagination:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                ChatSessionTagRepositoryListParams(**kwargs)

    def test_response_and_existing_chat_session_tags_are_models(self) -> None:
        tag = ChatSessionTagTable(id=3, value="comparison/1")
        self.assertEqual(ChatSessionTagResponse.model_validate(tag).value, "comparison/1")
        session = ChatSessionTable(id=1, dataset_conversation_id=2, tags=[tag])
        self.assertEqual(session.tags[0].value, "comparison/1")


class ChatSessionTagServiceRepositoryTests(unittest.TestCase):
    def test_service_delegates_all_operations(self) -> None:
        repository = FakeRepository()
        service = ChatSessionTagService(cast(Any, repository), cast(Any, NOOP_OBSERVABILITY))
        list_params = ChatSessionTagServiceListParams(offset=2, limit=3)
        get_params = ChatSessionTagServiceGetParams(chat_session_tag_id=7)
        create_params = ChatSessionTagServiceCreateParams(value="new")
        update_params = ChatSessionTagServiceUpdateParams(chat_session_tag_id=7, value="updated")
        run(service.list(list_params))
        run(service.get(get_params))
        run(service.create(create_params))
        run(service.update(update_params))
        run(service.delete(get_params))
        self.assertEqual(
            [name for name, _ in repository.calls], ["list", "get", "create", "update", "delete"]
        )
        self.assertIs(repository.calls[0][1], list_params)

    def test_repository_crud_uses_session_and_handles_missing_items(self) -> None:
        session = FakeSession()
        repository = ChatSessionTagRepository(cast(Any, session), cast(Any, NOOP_OBSERVABILITY))
        created = run(repository.create(ChatSessionTagRepositoryCreateParams(value="created")))
        self.assertEqual(created.value, "created")
        self.assertEqual((session.commits, session.refreshed), (1, 1))
        self.assertIsNotNone(
            run(
                repository.update(
                    ChatSessionTagRepositoryUpdateParams(chat_session_tag_id=1, value="new")
                )
            )
        )
        self.assertEqual(session.items[1].value, "new")
        self.assertTrue(
            run(repository.delete(ChatSessionTagRepositoryGetParams(chat_session_tag_id=1)))
        )
        self.assertFalse(
            run(repository.delete(ChatSessionTagRepositoryGetParams(chat_session_tag_id=99)))
        )
        self.assertIsNone(
            run(
                repository.update(
                    ChatSessionTagRepositoryUpdateParams(chat_session_tag_id=99, value="x")
                )
            )
        )
