import asyncio
import unittest
from types import SimpleNamespace
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
from src.module.chat_sessions.chat_sessions_repository_schema import (
    ChatSessionRepositoryUpdateParams,
)
from src.module.chat_sessions.chat_sessions_service_schema import (
    ChatSessionServiceCreateParams,
)
from src.platform.database.models import (
    ChatSessionTable,
    ChatSessionTagTable,
    ChatSessionToTagTable,
    DatasetConversationTable,
)
from src.platform.observability import NOOP_OBSERVABILITY, Observability


class ScalarResult:
    def __init__(self, scalar=None, rows=()):
        self.scalar = scalar
        self.rows = rows

    def scalar_one_or_none(self):
        return self.scalar

    def scalar_one(self):
        if self.scalar is None:
            raise AssertionError("expected a scalar result")
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self.rows)


class FakeSession:
    def __init__(
        self,
        *,
        session=True,
        doc_json='{"source":"full document"}',
        rows=(),
        agent_approach="baseline",
        model="gpt-5.6-luna",
    ):
        self.chat_session = (
            ChatSessionTable(
                id=7,
                dataset_conversation_id=3,
                agent_approach=agent_approach,
                prompt_version=(
                    "baseline-tool:v1" if agent_approach == "baseline-tool" else "baseline:v1"
                ),
                model=model,
            )
            if session
            else None
        )
        self.dataset = DatasetConversationTable(
            id=3, source_id="source", split="train", doc_json=doc_json
        )
        self.rows = rows
        self.execute_count = 0
        self.added = []
        self.sequence = []

    async def execute(self, statement):
        self.execute_count += 1
        if any(isinstance(item, ChatSessionTable) for item in self.added):
            return ScalarResult(self.added[0])
        if self.execute_count == 1:
            return ScalarResult(self.chat_session)
        return ScalarResult(rows=self.rows)

    async def get(self, model, identifier):
        return self.dataset

    def add(self, value):
        self.added.append(value)
        self.sequence.append(f"add:{getattr(value, 'role', '?')}")

    async def commit(self):
        self.sequence.append("commit")

    async def rollback(self):
        self.sequence.append("rollback")

    async def refresh(self, value):
        self.sequence.append("refresh")


class ChatSessionRepositoryTests(unittest.TestCase):
    def test_create_persists_selected_model(self) -> None:
        session = FakeSession()
        repository = ChatSessionRepository(
            cast(AsyncSession, session), cast(Observability, NOOP_OBSERVABILITY)
        )

        created = asyncio.run(
            repository.create(
                ChatSessionServiceCreateParams(
                    dataset_conversation_id=3,
                    agent_approach=AgentApproach.BASELINE,
                    model=OpenAIModel.GPT_5_6_SOL,
                )
            )
        )

        self.assertEqual(created.model, OpenAIModel.GPT_5_6_SOL)
        self.assertEqual(len(session.added), 1)
        self.assertEqual(session.added[0].model, "gpt-5.6-sol")
        self.assertEqual(session.sequence, ["add:?", "commit", "refresh"])

    def test_update_tag_only_preserves_title_and_replaces_associations(self) -> None:
        session = UpdateFakeSession(
            requested_tags=[ChatSessionTagTable(id=2, value="new")]
        )
        repository = ChatSessionRepository(
            cast(AsyncSession, session), cast(Observability, NOOP_OBSERVABILITY)
        )

        updated = asyncio.run(
            repository.update(
                ChatSessionRepositoryUpdateParams(
                    dataset_conversation_id=3,
                    chat_session_id=7,
                    tags=[{"value": "new"}],
                    tags_provided=True,
                    title_provided=False,
                )
            )
        )

        self.assertEqual(updated.title, "keep this title")
        self.assertTrue(session.associations_deleted)
        self.assertEqual([(row.chat_session_id, row.tag_id) for row in session.added], [(7, 2)])

    def test_update_empty_tags_clears_associations(self) -> None:
        session = UpdateFakeSession(requested_tags=[])
        repository = ChatSessionRepository(
            cast(AsyncSession, session), cast(Observability, NOOP_OBSERVABILITY)
        )

        asyncio.run(
            repository.update(
                ChatSessionRepositoryUpdateParams(
                    dataset_conversation_id=3,
                    chat_session_id=7,
                    tags=[],
                    tags_provided=True,
                    title_provided=False,
                )
            )
        )

        self.assertTrue(session.associations_deleted)
        self.assertEqual(session.added, [])


class UpdateFakeSession:
    def __init__(self, *, requested_tags: list[ChatSessionTagTable]) -> None:
        self.chat_session = ChatSessionTable(
            id=7,
            dataset_conversation_id=3,
            agent_approach="baseline",
            prompt_version="baseline:v1",
            model="gpt-5.6-luna",
            title="keep this title",
        )
        self.requested_tags = requested_tags
        self.execute_count = 0
        self.added: list[ChatSessionToTagTable] = []
        self.associations_deleted = False

    async def execute(self, statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return ScalarResult(self.chat_session)
        if self.execute_count == 3 and self.requested_tags:
            return ScalarResult(rows=self.requested_tags)
        if self.execute_count == (4 if self.requested_tags else 2):
            self.associations_deleted = True
            return ScalarResult()
        return ScalarResult(self.chat_session)

    def add(self, value) -> None:
        if isinstance(value, ChatSessionToTagTable):
            self.added.append(value)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None
