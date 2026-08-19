"""Transport-neutral preparation of immutable agent execution payloads."""

from collections.abc import Callable
from dataclasses import dataclass

from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import ChatApproach


@dataclass(frozen=True)
class PreparedApproach:
    approach: AgentApproach
    name: str
    instructions: str
    rendered_context: str
    model: str
    prompt_version: str
    prompt_hash: str
    context_version: str
    context_hash: str


class AgentExecutionPreparationService:
    def __init__(self, resolver: Callable[[AgentApproach], ChatApproach]) -> None:
        self._resolver = resolver

    def prepare(
        self,
        approach: AgentApproach,
        *,
        name: str,
        prompt_version: str,
        context_version: str,
        document: str,
        transcript: tuple[ConversationMessage, ...],
        question: str,
        model: str,
        expected_prompt_hash: str | None = None,
        expected_context_hash: str | None = None,
    ) -> PreparedApproach:
        obj: ChatApproach = self._resolver(approach)
        prompt = obj.resolve_prompt(prompt_version)
        rendered = obj.render_context(context_version, document, transcript, question)
        if expected_prompt_hash and expected_prompt_hash != prompt.content_hash:
            raise ValueError("Persisted prompt hash does not match the resolved prompt")
        if expected_context_hash and expected_context_hash != rendered.version.definition_hash:
            raise ValueError("Persisted context hash does not match the resolved context")
        return PreparedApproach(
            approach=approach,
            name=name,
            instructions=prompt.instructions,
            rendered_context=rendered.rendered,
            model=str(model),
            prompt_version=prompt.id,
            prompt_hash=prompt.content_hash,
            context_version=rendered.version.id,
            context_hash=rendered.version.definition_hash,
        )
