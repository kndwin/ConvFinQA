"""Schemas and protocol for running an agent approach."""

from collections.abc import AsyncIterator
from typing import Protocol

from ag_ui.core import BaseEvent
from pydantic import BaseModel, ConfigDict

from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage


class PromptVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    approach: AgentApproach
    instructions: str
    content_hash: str


class ContextVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    definition_hash: str


class RenderedContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: ContextVersion
    rendered: str


class ApproachInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt: PromptVersion
    context: RenderedContext
    model: str
    trace_metadata: dict[str, str]
    assistant_message_id: str
    transcript: tuple[ConversationMessage, ...]
    question: str
    # Private run input.  Approaches must never put this value in rendered context.
    document: str = ""


class ChatApproach(Protocol):
    @property
    def is_configured(self) -> bool: ...

    def resolve_prompt(self, prompt_id: str) -> PromptVersion: ...

    def render_context(
        self,
        version: str,
        document: str,
        transcript: tuple[ConversationMessage, ...],
        question: str,
    ) -> RenderedContext: ...

    def stream(self, input_data: ApproachInput) -> AsyncIterator[BaseEvent]:
        """Return an async iterator of AG-UI events produced by the approach."""
        ...
