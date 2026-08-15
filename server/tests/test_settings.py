import unittest

from src.platform.config.settings import async_database_url


class AsyncDatabaseUrlTests(unittest.TestCase):
    def test_normalizes_railway_postgresql_urls(self) -> None:
        self.assertEqual(
            async_database_url("postgresql://user:pass@host/db"),
            "postgresql+asyncpg://user:pass@host/db",
        )
        self.assertEqual(
            async_database_url("postgres://user:pass@host/db"),
            "postgresql+asyncpg://user:pass@host/db",
        )

    def test_preserves_async_and_empty_values(self) -> None:
        self.assertEqual(
            async_database_url("postgresql+asyncpg://user:pass@host/db"),
            "postgresql+asyncpg://user:pass@host/db",
        )
        self.assertIsNone(async_database_url(None))
