"""No-network tests for the Temporal OpenAI Agents integration."""

import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from agents import ModelResponse
from src.module.agent_execution.execution.durable.durable_agent_workflow import (
    DurableAgentWorkflow,
)
from src.module.agent_execution.execution.durable.durable_agent_workflow_schema import (
    DurableAgentWorkflowInput,
)
from src.platform.config.settings import Settings
from src.platform.temporal.plugin import create_model_activity_parameters
from temporalio.client import WorkflowFailureError
from temporalio.contrib.openai_agents.testing import (
    AgentEnvironment,
    ResponseBuilders,
    TestModel,
)
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker


def _request(execution_id: str = "test-execution") -> DurableAgentWorkflowInput:
    return DurableAgentWorkflowInput(
        execution_id=execution_id,
        model="fake-model",
        agent_name="test-agent",
        instructions="Answer briefly.",
        rendered_context="Say hello.",
        trace_metadata={"test": "true"},
    )


def _settings() -> Settings:
    return Settings(
        temporal_model_schedule_to_close_seconds=30,
        temporal_model_start_to_close_seconds=10,
        temporal_model_heartbeat_seconds=5,
        temporal_model_max_attempts=2,
    )


class TemporalDurableAgentTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.environment_patch = patch.dict(os.environ)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        os.environ.pop("OPENAI_API_KEY", None)
        self.assertNotIn("OPENAI_API_KEY", os.environ)

    async def test_success_uses_plugin_model_activity_and_reports_status(self) -> None:
        model = TestModel.returning_responses([ResponseBuilders.output_message("hello")])
        async with (
            await WorkflowEnvironment.start_time_skipping() as environment,
            AgentEnvironment(
                model=model,
                model_params=create_model_activity_parameters(_settings()),
            ) as agent_environment,
        ):
            client = agent_environment.applied_on_client(environment.client)
            async with Worker(
                client,
                task_queue="durable-agent-tests",
                workflows=[DurableAgentWorkflow],
            ):
                handle = await client.start_workflow(
                    DurableAgentWorkflow.run,
                    _request(),
                    id="durable-agent-success",
                    task_queue="durable-agent-tests",
                )
                result = await handle.result()
                self.assertEqual(result.final_output, "hello")
                status = (await handle.describe()).status
                self.assertIsNotNone(status)
                assert status is not None
                self.assertEqual(status.name, "COMPLETED")

                activity_names: list[str] = []
                async for event in handle.fetch_history_events():
                    if event.HasField("activity_task_scheduled_event_attributes"):
                        activity_names.append(
                            event.activity_task_scheduled_event_attributes.activity_type.name
                        )
                self.assertIn("invoke_model_activity", activity_names)

                history = await handle.fetch_history()
                await Replayer(
                    workflows=[DurableAgentWorkflow],
                    plugins=[agent_environment.openai_agents_plugin],
                ).replay_workflow(history)

    async def test_transient_provider_failure_is_retried_once(self) -> None:
        attempts = 0

        def response() -> ModelResponse:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary fake provider failure")
            return ResponseBuilders.output_message("recovered")

        async with (
            await WorkflowEnvironment.start_time_skipping() as environment,
            AgentEnvironment(
                model=TestModel(response),
                model_params=create_model_activity_parameters(_settings()),
            ) as agent_environment,
        ):
            client = agent_environment.applied_on_client(environment.client)
            async with Worker(
                client,
                task_queue="durable-agent-tests",
                workflows=[DurableAgentWorkflow],
            ):
                handle = await client.start_workflow(
                    DurableAgentWorkflow.run,
                    _request("transient"),
                    id="durable-agent-transient",
                    task_queue="durable-agent-tests",
                )
                self.assertEqual((await handle.result()).final_output, "recovered")
        self.assertEqual(attempts, 2)

    async def test_permanent_provider_failure_is_not_retried(self) -> None:
        attempts = 0

        def response() -> ModelResponse:
            nonlocal attempts
            attempts += 1
            raise ApplicationError("permanent fake provider failure", non_retryable=True)

        async with (
            await WorkflowEnvironment.start_time_skipping() as environment,
            AgentEnvironment(
                model=TestModel(response),
                model_params=create_model_activity_parameters(_settings()),
            ) as agent_environment,
        ):
            client = agent_environment.applied_on_client(environment.client)
            async with Worker(
                client,
                task_queue="durable-agent-tests",
                workflows=[DurableAgentWorkflow],
            ):
                handle = await client.start_workflow(
                    DurableAgentWorkflow.run,
                    _request("permanent"),
                    id="durable-agent-permanent",
                    task_queue="durable-agent-tests",
                )
                with self.assertRaises(WorkflowFailureError):
                    await handle.result()
        self.assertEqual(attempts, 1)

    async def test_queued_workflow_can_be_cancelled(self) -> None:
        async with (
            await WorkflowEnvironment.start_time_skipping() as environment,
            AgentEnvironment(
                model=TestModel.returning_responses([]),
                model_params=create_model_activity_parameters(_settings()),
                register_activities=False,
            ) as agent_environment,
        ):
            client = agent_environment.applied_on_client(environment.client)
            async with Worker(
                client,
                task_queue="cancel-durable-agent-tests",
                workflows=[DurableAgentWorkflow],
            ):
                handle = await client.start_workflow(
                    DurableAgentWorkflow.run,
                    _request("cancelled"),
                    id="durable-agent-cancelled",
                    task_queue="cancel-durable-agent-tests",
                )
                await handle.cancel()
                with self.assertRaises(WorkflowFailureError):
                    await handle.result()
                status = (await handle.describe()).status
                self.assertIsNotNone(status)
                assert status is not None
                self.assertEqual(status.name, "CANCELED")
