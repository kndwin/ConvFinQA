from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent
from openai import AsyncOpenAI

from src.module.agent_execution.agent_approach.baseline.run import BaselineApproach
from src.module.agent_execution.agent_approach.baseline_tool.run import BaselineToolApproach
from src.module.agent_execution.agent_approach.program_of_thought.run import (
    ProgramOfThoughtApproach,
)
from src.module.agent_execution.agent_approach.shared.tools.code_execution.openai_provider import (
    OpenAICodeExecutionProvider,
)
from src.module.agent_execution.agent_approach.shared.tools.code_execution.provider import (
    CodeExecutionProvider,
)
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_repository import AgentExecutionRepository
from src.module.agent_execution.agent_execution_runner import AgentExecutionRunner
from src.module.agent_execution.agent_execution_service_schema import AgentExecutionServiceRunParams


class AgentExecutionService:
    def __init__(
        self,
        client: AsyncOpenAI | None,
        code_execution_provider: CodeExecutionProvider | None = None,
    ) -> None:
        # Keep the approach present even when configuration is absent.  The runner
        # owns the common configuration error (and can therefore report it for
        # every approach consistently).
        program = ProgramOfThoughtApproach(
            client, code_execution_provider or OpenAICodeExecutionProvider()
        )
        self.runner = AgentExecutionRunner(
            BaselineApproach(client), BaselineToolApproach(client), program
        )

    def resolve_approach(self, value: AgentApproach):
        return self.runner.resolve_approach(value)

    async def run(
        self, params: AgentExecutionServiceRunParams, repository: AgentExecutionRepository
    ) -> AsyncIterator[BaseEvent]:
        async for event in self.runner.run(params, repository):
            yield event
