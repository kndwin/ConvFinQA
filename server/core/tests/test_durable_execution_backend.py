"""Unit tests for the Temporal-independent durable execution facade."""

from datetime import timedelta
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from src.module.agent_execution.execution.durable.durable_execution_backend import (
    DurableExecutionBackend,
)


async def _workflow(_: object) -> None:
    return None


class DurableExecutionBackendTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.backend = DurableExecutionBackend()
        self.client = MagicMock()
        self.client.start_workflow = AsyncMock()
        self.backend.client = AsyncMock(return_value=self.client)  # type: ignore[method-assign]

    async def test_start_workflow_delegates_all_arguments(self) -> None:
        workflow_input = {"value": "input"}
        timeout = timedelta(minutes=3)

        await self.backend.start_workflow(
            _workflow,
            workflow_input,
            "workflow-id",
            "task-queue",
            timeout,
        )

        self.client.start_workflow.assert_awaited_once_with(
            _workflow,
            workflow_input,
            id="workflow-id",
            task_queue="task-queue",
            execution_timeout=timeout,
        )

    async def test_start_workflow_treats_already_started_as_success(self) -> None:
        class AlreadyStarted(Exception):
            pass

        self.client.start_workflow.side_effect = AlreadyStarted()
        with patch(
            "src.module.agent_execution.execution.durable.durable_execution_backend.WorkflowAlreadyStartedError",
            AlreadyStarted,
        ):
            await self.backend.start_workflow(
                _workflow, {}, "workflow-id", "task-queue", timedelta(seconds=1)
            )

    async def test_handle_and_typed_handle_delegate_to_client(self) -> None:
        untyped_handle = object()
        typed_handle = object()
        self.client.get_workflow_handle.return_value = untyped_handle
        self.client.get_workflow_handle_for.return_value = typed_handle

        self.assertIs(untyped_handle, await self.backend.handle("workflow-id"))
        self.assertIs(typed_handle, await self.backend.typed_handle(_workflow, "workflow-id"))

        self.client.get_workflow_handle.assert_called_once_with("workflow-id")
        self.client.get_workflow_handle_for.assert_called_once_with(_workflow, "workflow-id")

    async def test_subscribe_creates_stream_and_yields_items(self) -> None:
        async def stream_items():
            yield "first"
            yield "second"

        stream = MagicMock()
        stream.subscribe.return_value = stream_items()
        with patch(
            "src.module.agent_execution.execution.durable.durable_execution_backend.WorkflowStreamClient.create",
            return_value=stream,
        ) as create:
            result = [
                item
                async for item in self.backend.subscribe("workflow-id", "updates", from_offset=4)
            ]

        self.assertEqual(result, ["first", "second"])
        create.assert_called_once_with(self.client, "workflow-id")
        stream.subscribe.assert_called_once_with(topics="updates", from_offset=4)
