from src.module.agent_execution.agent_execution_runner_schema import RenderedContext

from .document_conversation import render

CONTEXT_VERSION = "document-conversation:v1"


def resolve(version: str, document: str, transcript, question: str) -> RenderedContext:
    if version != CONTEXT_VERSION:
        raise ValueError(f"Unsupported context version: {version}")
    return render(document, tuple(transcript), question)
