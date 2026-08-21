import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import agents
from agents.models.interface import ModelProvider
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI

from src.platform.config.settings import config


@asynccontextmanager
async def model_provider() -> AsyncIterator[ModelProvider | None]:
    """Provide the application-owned model provider, when configured."""
    if not config.openai_api_key:
        yield None
        return

    agents.set_tracing_export_api_key(config.openai_api_key)
    client = AsyncOpenAI(api_key=config.openai_api_key)
    try:
        yield OpenAIProvider(openai_client=client)
    finally:
        await asyncio.shield(client.close())
