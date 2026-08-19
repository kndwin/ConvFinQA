"""Temporal client factory (no client is created at import time)."""

from agents import ModelProvider
from temporalio.client import Client

from src.platform.config.settings import Settings
from src.platform.temporal.plugin import create_openai_agents_plugin


async def connect_temporal(
    settings: Settings, *, model_provider: ModelProvider | None = None
) -> Client:
    """Connect a client with the same plugin/data converter as the worker."""
    return await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        plugins=[create_openai_agents_plugin(settings, model_provider=model_provider)],
    )
