import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import agents
from openai import AsyncOpenAI

from src.platform.config.settings import config


@asynccontextmanager
async def openai_client() -> AsyncIterator[AsyncOpenAI | None]:
    """Provide the application-owned OpenAI client, when configured."""
    if not config.openai_api_key:
        yield None
        return

    agents.set_tracing_export_api_key(config.openai_api_key)
    client = AsyncOpenAI(api_key=config.openai_api_key)
    try:
        yield client
    finally:
        await asyncio.shield(client.close())
