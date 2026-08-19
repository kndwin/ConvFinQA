"""Separate process entry point for the durable agent Temporal Worker."""

import asyncio

import agents
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI
from temporalio.worker import Worker

from src.module.agent_execution.execution.durable.durable_agent_workflow import DurableAgentWorkflow
from src.module.agent_execution.execution.durable.ensemble_workflow import (
    EnsembleWorkflow,
)
from src.module.chat_sessions.run_finalization_activities import (
    fail_ensemble_run,
    finalize_ensemble_run,
)
from src.platform.config.settings import Settings
from src.platform.temporal.client import connect_temporal


async def run_worker() -> None:
    settings = Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY must be set in server/.env for the Temporal Worker")
    agents.set_tracing_export_api_key(settings.openai_api_key)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0)
    try:
        client = await connect_temporal(
            settings, model_provider=OpenAIProvider(openai_client=openai_client)
        )
        async with Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[DurableAgentWorkflow, EnsembleWorkflow],
            activities=[finalize_ensemble_run, fail_ensemble_run],
            max_concurrent_activities=settings.temporal_max_concurrent_activities,
        ):
            await asyncio.Future()
    finally:
        await asyncio.shield(openai_client.close())


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
