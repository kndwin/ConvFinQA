import asyncio
import unittest
from types import SimpleNamespace

from sqlalchemy.dialects import sqlite

from src.module.dataset_conversations.dataset_conversations_repository import (
    DatasetConversationRepository,
)
from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryListParams,
)
from src.platform.observability import NOOP_OBSERVABILITY


class DatasetConversationRepositoryQueryTests(unittest.TestCase):
    def test_tag_filter_is_single_correlated_exists_before_pagination(self):
        class Session:
            statement = None

            async def execute(self, statement):
                self.statement = statement
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

        session = Session()
        repository = DatasetConversationRepository(session, NOOP_OBSERVABILITY)
        asyncio.run(
            repository.list(
                DatasetConversationRepositoryListParams(offset=4, limit=6, tags=["a", "b"])
            )
        )
        sql = str(session.statement.compile(dialect=sqlite.dialect()))
        self.assertEqual(sql.upper().count("EXISTS"), 1)
        self.assertIn(" IN (", sql.upper())
        self.assertLess(sql.upper().index("WHERE"), sql.upper().index("LIMIT"))
        self.assertLess(sql.upper().index("WHERE"), sql.upper().index("OFFSET"))
