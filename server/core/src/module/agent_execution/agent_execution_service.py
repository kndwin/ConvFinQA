from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent
from agents.models.interface import ModelProvider

from src.module.agent_execution.agent_approach.baseline.run import BaselineApproach
from src.module.agent_execution.agent_approach.baseline_tool.run import BaselineToolApproach
from src.module.agent_execution.agent_approach.evidence.run import EvidenceApproach
from src.module.agent_execution.agent_approach.program_of_thought.run import (
    ProgramOfThoughtApproach,
)
from src.module.agent_execution.agent_approach.shared.tools.code_execution.provider import (
    CodeExecutionProvider,
)
from src.module.agent_execution.agent_execution_repository import AgentExecutionRepository
from src.module.agent_execution.agent_execution_runner import AgentExecutionRunner
from src.module.agent_execution.agent_execution_service_schema import AgentExecutionServiceRunParams


class AgentExecutionService:
    def __init__(
        self,
        model_provider: ModelProvider | None,
        code_execution_provider: CodeExecutionProvider | None = None,
    ) -> None:
        program = (
            ProgramOfThoughtApproach(model_provider, code_execution_provider)
            if code_execution_provider is not None
            else None
        )
        self.runner = AgentExecutionRunner(
            BaselineApproach(model_provider), BaselineToolApproach(model_provider), program,
            EvidenceApproach(model_provider)
        )

    async def run(
        self, params: AgentExecutionServiceRunParams, repository: AgentExecutionRepository
    ) -> AsyncIterator[BaseEvent]:
        async for event in self.runner.run(params, repository):
            yield event
