import hashlib
import json

from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import ContextVersion, RenderedContext

CONTEXT_VERSION = "conversation-question:v1"
CONTEXT_DEFINITION = "ordered conversation messages plus current question; source document excluded"
VERSION = ContextVersion(
    id=CONTEXT_VERSION,
    definition_hash=hashlib.sha256(CONTEXT_DEFINITION.encode()).hexdigest(),
)


def resolve(
    version: str = CONTEXT_VERSION,
    document: str = "",
    transcript: tuple[ConversationMessage, ...] = (),
    question: str = "",
) -> RenderedContext:
    # Existing API clients send the global document context version. Evidence
    # intentionally maps it to its document-free rendering at the boundary.
    if version not in {CONTEXT_VERSION, "document-conversation:v1"}:
        raise ValueError(f"Unsupported context version: {version}")
    # Deliberately do not reference document. This is the model-visible boundary.
    history = [{"role": m.role, "content": m.content} for m in transcript]
    rendered = json.dumps({"conversation": history, "question": question}, ensure_ascii=False)
    return RenderedContext(version=VERSION, rendered=rendered)
