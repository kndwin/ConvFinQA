import hashlib

from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import (
    ContextVersion,
    RenderedContext,
)

TEMPLATE_DEFINITION = "document-conversation:v1|history|document|question|xml-v1"
VERSION = ContextVersion(
    id="document-conversation:v1",
    definition_hash=hashlib.sha256(TEMPLATE_DEFINITION.encode()).hexdigest(),
)


def render(
    document: str, transcript: tuple[ConversationMessage, ...], question: str
) -> RenderedContext:
    history = "\n".join(f"{message.role}: {message.content}" for message in transcript)
    prefix = f"<conversation_history>\n{history}\n</conversation_history>\n" if history else ""
    return RenderedContext(
        version=VERSION,
        rendered=(
            f"{prefix}<document_context>\n{document}\n</document_context>\n"
            f"<user_question>\n{question}\n</user_question>"
        ),
    )
