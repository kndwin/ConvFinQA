"""Reusable Temporal client and workflow-handle mechanics.

This module intentionally knows nothing about application repositories or chat sessions.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from datetime import timedelta
from typing import Any

from temporalio.client import Client
from temporalio.contrib.workflow_streams import WorkflowStreamClient
from temporalio.exceptions import WorkflowAlreadyStartedError

from src.platform.config import config
from src.platform.temporal.client import connect_temporal


class TemporalUnavailableError(RuntimeError):
    pass


class DurableExecutionBackend:
    def __init__(self) -> None:
        self._client: Client | None = None

    async def client(self) -> Client:
        if not config.temporal_enabled:
            raise TemporalUnavailableError("Temporal execution is disabled")
        if self._client is None:
            try:
                self._client = await connect_temporal(config)
            except Exception as exc:
                raise TemporalUnavailableError("Temporal is unavailable") from exc
        return self._client

    async def preflight(self) -> None:
        """Ensure that durable execution is enabled and reachable."""
        await self.client()

    async def start_workflow(
        self,
        workflow: Callable[..., Any],
        workflow_input: Any,
        workflow_id: str,
        task_queue: str,
        execution_timeout: timedelta,
    ) -> None:
        """Start a workflow, treating an existing workflow as success."""
        with suppress(WorkflowAlreadyStartedError):
            await (await self.client()).start_workflow(
                workflow,
                workflow_input,
                id=workflow_id,
                task_queue=task_queue,
                execution_timeout=execution_timeout,
            )

    async def handle(self, workflow_id: str) -> Any:
        return (await self.client()).get_workflow_handle(workflow_id)

    async def typed_handle(self, workflow: Callable[..., Any], workflow_id: str) -> Any:
        return (await self.client()).get_workflow_handle_for(workflow, workflow_id)

    async def subscribe(
        self, workflow_id: str, topic: str, from_offset: int = 0
    ) -> AsyncIterator[Any]:
        """Subscribe to a workflow stream without exposing Temporal to callers."""
        stream = WorkflowStreamClient.create(await self.client(), workflow_id)
        async for item in stream.subscribe(topics=topic, from_offset=from_offset):
            yield item
