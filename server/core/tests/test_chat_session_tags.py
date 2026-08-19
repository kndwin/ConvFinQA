import asyncio
import builtins
import unittest
from types import SimpleNamespace
from typing import Any, cast

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from src.main import create_app
from src.module.chat_session_tags.chat_session_tags_repository import ChatSessionTagRepository
from src.module.chat_session_tags.chat_session_tags_repository_schema import (
    ChatSessionTagRepositoryCreateParams,
    ChatSessionTagRepositoryGetParams,
    ChatSessionTagRepositoryListParams,
    ChatSessionTagRepositoryUpdateParams,
)
from src.module.chat_session_tags.chat_session_tags_router import router
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


def route(path: str, method: str) -> Any:
    return next(
        cast(Any, r).endpoint.__dishka_orig_func__
        for r in router.routes
        if cast(Any, r).path == path and method in cast(Any, r).methods
    )


class ChatSessionTagRouterTests(unittest.TestCase):
    def test_openapi_exposes_collection_and_item_crud_contract(self) -> None:
        schema = create_app().openapi()
        paths = schema["paths"]
        self.assertEqual(set(paths["/chat-session-tags"]), {"get", "post"})
        self.assertEqual(
            set(paths["/chat-session-tags/{chat_session_tag_id}"]), {"get", "patch", "delete"}
        )
        components = schema["components"]["schemas"]
        self.assertEqual(components["ChatSessionTagRequest"]["required"], ["value"])
        self.assertEqual(components["ChatSessionTagResponse"]["required"], ["id", "value"])
        parameters = {
            parameter["name"]: parameter
            for parameter in paths["/chat-session-tags"]["get"]["parameters"]
        }
        self.assertEqual(parameters["offset"]["schema"]["default"], 0)
        self.assertEqual(parameters["limit"]["schema"]["default"], 20)
        self.assertEqual(parameters["limit"]["schema"]["maximum"], 100)
        self.assertEqual(
            paths["/chat-session-tags/{chat_session_tag_id}"]["delete"]["responses"]["204"][
                "description"
            ],
            "Successful Response",
        )
        self.assertEqual(
            paths["/chat-session-tags"]["post"]["responses"]["201"]["content"]["application/json"][
                "schema"
            ]["$ref"],
            "#/components/schemas/ChatSessionTagResponse",
        )

    def test_list_defaults_and_missing_item_operations_return_404(self) -> None:
        service = FakeRepository()
        listed = run(route("/chat-session-tags", "GET")(service, 0, 20))
        self.assertEqual(listed[0].value, "one")

        class Missing:
            async def get(self, _params: Any) -> None:
                return None

            async def update(self, _params: Any) -> None:
                return None

            async def delete(self, _params: Any) -> bool:
                return False

        missing = Missing()
        for operation in (
            lambda: route("/chat-session-tags/{chat_session_tag_id}", "GET")(9, service=missing),
            lambda: route("/chat-session-tags/{chat_session_tag_id}", "PATCH")(
                9, ChatSessionTagRequest(value="x"), service=missing
            ),
            lambda: route("/chat-session-tags/{chat_session_tag_id}", "DELETE")(9, service=missing),
        ):
            with (
                self.subTest(operation=operation),
                self.assertRaisesRegex(HTTPException, "not found") as context,
            ):
                run(operation())
            self.assertEqual(context.exception.status_code, 404)

    def test_duplicate_create_and_update_map_integrity_error_to_409(self) -> None:
        duplicate = SimpleNamespace(
            create=lambda _params: (_ for _ in ()).throw(IntegrityError("x", {}, Exception())),
            update=lambda _params: (_ for _ in ()).throw(IntegrityError("x", {}, Exception())),
        )
        with self.assertRaises(HTTPException) as create_error:
            run(
                route("/chat-session-tags", "POST")(
                    ChatSessionTagRequest(value="x"), service=duplicate
                )
            )
        with self.assertRaises(HTTPException) as update_error:
            run(
                route("/chat-session-tags/{chat_session_tag_id}", "PATCH")(
                    1, ChatSessionTagRequest(value="x"), service=duplicate
                )
            )
        self.assertEqual(
            create_error.exception.status_code, update_error.exception.status_code, 409
        )


if __name__ == "__main__":
    unittest.main()
