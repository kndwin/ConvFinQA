from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage


class AgentExecutionRepository(Protocol):
    async def messages(self) -> Sequence[ConversationMessage]: ...
    async def append_user(self, content: str, client_message_id: str | None = None) -> None: ...
    async def append_assistant(self, content: str) -> None: ...


MessagesCallback = Callable[[], Awaitable[Sequence[ConversationMessage]]]
UserCallback = Callable[[str, str | None], Awaitable[None]]
AssistantCallback = Callable[[str], Awaitable[None]]


class CallbackAgentExecutionRepository:
    def __init__(
        self,
        messages: MessagesCallback,
        append_user: UserCallback,
        append_assistant: AssistantCallback,
    ) -> None:
        self._messages, self._append_user, self._append_assistant = (
            messages,
            append_user,
            append_assistant,
        )

    async def messages(self) -> Sequence[ConversationMessage]:
        return await self._messages()

    async def append_user(self, content: str, client_message_id: str | None = None) -> None:
        await self._append_user(content, client_message_id)

    async def append_assistant(self, content: str) -> None:
        await self._append_assistant(content)


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
