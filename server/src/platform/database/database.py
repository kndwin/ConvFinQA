"""Asynchronous PostgreSQL engine and request-scoped sessions."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.platform.config import config

DATABASE_URL = config.database_url
assert DATABASE_URL is not None
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def database_lifespan():
    """Keep the database engine alive and dispose it on application shutdown."""
    try:
        yield
    finally:
        await engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield one session per request and roll back failed requests."""
    async with session_factory() as session:
        try:
            yield session
        except BaseException:
            # CancelledError inherits from BaseException. Shielding the rollback
            # lets a cancelled request release its transaction before re-raising.
            await asyncio.shield(session.rollback())
            raise
