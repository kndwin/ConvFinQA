import asyncio
import builtins
import unittest
from types import SimpleNamespace
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.main import create_app
from src.module.chat_session_tags.chat_session_tags_router import router
from src.module.chat_session_tags.chat_session_tags_router_schema import (
    ChatSessionTagRequest,
)
from src.platform.database.models import (
    ChatSessionTagTable,
)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def route(path: str, method: str) -> Any:
    return next(
        cast(Any, r).endpoint.__dishka_orig_func__
        for r in router.routes
        if cast(Any, r).path == path and method in cast(Any, r).methods
    )


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
