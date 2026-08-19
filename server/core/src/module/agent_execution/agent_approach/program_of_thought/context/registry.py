from src.module.agent_execution.agent_approach.shared.context.registry import resolve as _resolve
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import RenderedContext

CONTEXT_VERSION = "document-conversation:v1"


def resolve(
    version: str = CONTEXT_VERSION,
    document: str = "",
    transcript: tuple[ConversationMessage, ...] = (),
    question: str = "",
) -> RenderedContext:
    return _resolve(version, document, transcript, question)
