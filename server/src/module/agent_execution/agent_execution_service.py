from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent
from openai import AsyncOpenAI

from src.module.agent_execution.agent_approach.baseline.run import BaselineApproach
from src.module.agent_execution.agent_approach.baseline_tool.run import BaselineToolApproach
from src.module.agent_execution.agent_execution_repository import AgentExecutionRepository
from src.module.agent_execution.agent_execution_runner import AgentExecutionRunner
from src.module.agent_execution.agent_execution_service_schema import AgentExecutionServiceRunParams


class AgentExecutionService:
    def __init__(self, client: AsyncOpenAI | None) -> None:
        self.runner = AgentExecutionRunner(BaselineApproach(client), BaselineToolApproach(client))

    async def run(
        self, params: AgentExecutionServiceRunParams, repository: AgentExecutionRepository
    ) -> AsyncIterator[BaseEvent]:
        async for event in self.runner.run(params, repository):
            yield event
