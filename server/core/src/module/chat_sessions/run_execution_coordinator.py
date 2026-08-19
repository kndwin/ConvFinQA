"""Public application boundary choosing direct or durable execution."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from ag_ui.core import BaseEvent, RunAgentInput

from src.module.agent_execution.agent_execution_constants import AgentApproach, ExecutionMode
from src.module.chat_sessions.chat_session_run_adapter import ChatSessionRunAdapter
from src.module.chat_sessions.chat_sessions_service import ChatSessionService


@dataclass(frozen=True)
class RunExecutionPlan:
    mode: ExecutionMode
    workflow_id: str | None = None
    candidate_names: tuple[str, ...] = ()


class RunExecutionCoordinator:
    def __init__(self, sessions: ChatSessionService, durable: ChatSessionRunAdapter) -> None:
        self.sessions, self.durable = sessions, durable

    def mode_for(self, approach: AgentApproach | str) -> ExecutionMode:
        """Return the supported execution policy for an agent approach."""
        value = AgentApproach(approach)
        if value is AgentApproach.ENSEMBLE:
            return ExecutionMode.DURABLE
        return ExecutionMode.DIRECT

    async def prepare(
        self,
        dataset_id: int,
        chat_id: int,
        data: RunAgentInput,
        mode: ExecutionMode | None = None,
    ) -> RunExecutionPlan:
        session = await self.sessions.get_by_ids(dataset_id, chat_id)
        if session is None:
            raise LookupError("chat session not found")
        selected_mode = self.mode_for(session.agent_approach)
        if mode is not None and mode is not selected_mode:
            raise ValueError(f"Execution mode {mode} is not supported for {session.agent_approach}")
        if selected_mode is ExecutionMode.DURABLE:
            workflow_id = await self.durable.prepare_start(dataset_id, chat_id, data)
            candidates = await self.durable.candidate_names(dataset_id, chat_id)
            return RunExecutionPlan(ExecutionMode.DURABLE, workflow_id, candidates)
        return RunExecutionPlan(ExecutionMode.DIRECT)

    async def stream(
        self, plan: RunExecutionPlan, dataset_id: int, chat_id: int, data: RunAgentInput
    ) -> AsyncIterator[BaseEvent]:
        if plan.mode is ExecutionMode.DURABLE:
            assert plan.workflow_id is not None
            async for event in self.durable.stream_events(
                plan.workflow_id, data.thread_id, data.run_id, plan.candidate_names
            ):
                yield event
            return
        async for event in self.sessions.run(dataset_id, chat_id, data):
            yield event
