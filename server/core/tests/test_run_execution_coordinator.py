from types import SimpleNamespace
from typing import Any, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from ag_ui.core import RunAgentInput, UserMessage
from src.module.agent_execution.agent_execution_constants import AgentApproach, ExecutionMode
from src.module.chat_sessions.run_execution_coordinator import RunExecutionCoordinator


def request() -> RunAgentInput:
    return RunAgentInput(
        thread_id="thread",
        run_id="run",
        state={},
        messages=[UserMessage(id="message", content="question")],
        tools=[],
        context=[],
        forwarded_props={},
    )


class RunExecutionCoordinatorTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.sessions = SimpleNamespace(
            get_by_ids=AsyncMock(), run=Mock(return_value=self._events("direct"))
        )
        self.durable = SimpleNamespace(
            prepare_start=AsyncMock(return_value="workflow:run"),
            candidate_names=AsyncMock(return_value=("baseline", "baseline-tool")),
            stream_events=Mock(return_value=self._events("durable")),
        )
        self.coordinator = RunExecutionCoordinator(
            cast(Any, self.sessions), cast(Any, self.durable)
        )

    @staticmethod
    async def _events(value: str):
        yield value

    def test_mode_for_all_approaches(self) -> None:
        for approach in AgentApproach:
            expected = (
                ExecutionMode.DURABLE
                if approach is AgentApproach.ENSEMBLE
                else ExecutionMode.DIRECT
            )
            with self.subTest(approach=approach):
                self.assertIs(self.coordinator.mode_for(approach), expected)

    async def test_prepare_delegates_direct_by_returning_direct_plan(self) -> None:
        self.sessions.get_by_ids.return_value = SimpleNamespace(
            agent_approach=AgentApproach.BASELINE
        )

        plan = await self.coordinator.prepare(1, 2, request())

        self.assertEqual(plan.mode, ExecutionMode.DIRECT)
        self.durable.prepare_start.assert_not_awaited()

    async def test_stream_delegates_direct_execution(self) -> None:
        plan = cast(Any, SimpleNamespace(mode=ExecutionMode.DIRECT))
        events = [event async for event in self.coordinator.stream(plan, 1, 2, request())]

        self.assertEqual(events, ["direct"])
        self.sessions.run.assert_called_once_with(1, 2, request())

    async def test_prepare_delegates_durable_execution(self) -> None:
        self.sessions.get_by_ids.return_value = SimpleNamespace(
            agent_approach=AgentApproach.ENSEMBLE
        )

        plan = await self.coordinator.prepare(1, 2, request())

        self.durable.prepare_start.assert_awaited_once()
        self.durable.candidate_names.assert_awaited_once_with(1, 2)
        self.assertEqual(plan.mode, ExecutionMode.DURABLE)
        self.assertEqual(plan.workflow_id, "workflow:run")
        self.assertEqual(plan.candidate_names, ("baseline", "baseline-tool"))

    async def test_stream_delegates_durable_execution(self) -> None:
        plan = cast(
            Any,
            SimpleNamespace(
                mode=ExecutionMode.DURABLE,
                workflow_id="workflow:run",
                candidate_names=("baseline",),
            ),
        )
        events = [event async for event in self.coordinator.stream(plan, 1, 2, request())]

        self.assertEqual(events, ["durable"])
        self.durable.stream_events.assert_called_once_with(
            "workflow:run", "thread", "run", ("baseline",)
        )

    async def test_prepare_rejects_explicit_unsupported_mode(self) -> None:
        self.sessions.get_by_ids.return_value = SimpleNamespace(
            agent_approach=AgentApproach.BASELINE
        )

        with self.assertRaises(ValueError):
            await self.coordinator.prepare(1, 2, request(), ExecutionMode.DURABLE)

        self.durable.prepare_start.assert_not_awaited()

    async def test_prepare_rejects_missing_session(self) -> None:
        self.sessions.get_by_ids.return_value = None

        with self.assertRaises(LookupError):
            await self.coordinator.prepare(1, 2, request())
