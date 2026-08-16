from collections.abc import Sequence

from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage


class InMemoryAgentExecutionRepository:
    def __init__(self) -> None:
        self._messages: list[ConversationMessage] = []

    async def messages(self) -> Sequence[ConversationMessage]:
        return tuple(self._messages)

    async def append_user(self, content: str, client_message_id: str | None = None) -> None:
        self._messages.append(
            ConversationMessage(role="user", content=content, message_id=client_message_id)
        )

    async def append_assistant(self, content: str) -> None:
        self._messages.append(ConversationMessage(role="assistant", content=content))
