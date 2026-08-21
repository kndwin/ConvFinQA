from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent
from src.module.agent_execution.agent_approach.baseline.context.registry import (
    resolve as resolve_context,
)
from src.module.agent_execution.agent_approach.baseline.prompts.registry import (
    resolve as resolve_prompt,
)
from src.module.agent_execution.agent_approach.baseline.structured_output import (
    StructuredAnswer,
)
from src.module.agent_execution.agent_approach.shared.agent_builder import build_agent
from src.module.agent_execution.agent_approach.shared.base_agent_approach import BaseAgentApproach
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import (
    ApproachInput,
    PromptVersion,
    RenderedContext,
)


class BaselineApproach(BaseAgentApproach):
    def resolve_prompt(self, prompt_id: str = "baseline:v1") -> PromptVersion:
        return resolve_prompt(prompt_id)

    def render_context(
        self,
        version: str,
        document: str,
        transcript: tuple[ConversationMessage, ...],
        question: str,
    ) -> RenderedContext:
        return resolve_context(version, document, transcript, question)

    def stream(self, input_data: ApproachInput) -> AsyncIterator[BaseEvent]:
        output_type = {
            "baseline:v3": StructuredAnswer,
        }.get(input_data.prompt.id)
        agent = build_agent(
            name="ConvFinQA baseline document assistant",
            model=input_data.model,
            instructions=input_data.prompt.instructions,
            output_type=output_type,
        )
        return (self._events_structured if output_type else self._events)(
            input_data, self._stream(input_data, agent, 1, "ConvFinQA document chat")
        )
