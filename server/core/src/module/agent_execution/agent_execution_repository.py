from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.platform.observability import Observability, get_observability, trace_method


class AgentExecutionRepository(Protocol):
    """
    Interface for storing messages from agentic outputs
    """

    async def messages(self) -> Sequence[ConversationMessage]: ...
    async def append_user(self, content: str, client_message_id: str | None = None) -> None: ...
    async def append_assistant(self, content: str) -> None: ...


MessagesCallback = Callable[[], Awaitable[Sequence[ConversationMessage]]]
UserCallback = Callable[[str, str | None], Awaitable[None]]
AssistantCallback = Callable[[str], Awaitable[None]]


class CallbackAgentExecutionRepository:
    """
    CallbackAgentExecutionRepository is used for production
    """

    def __init__(
        self,
        messages: MessagesCallback,
        append_user: UserCallback,
        append_assistant: AssistantCallback,
        observability: Observability | None = None,
    ) -> None:
        self.observability = observability if observability is not None else get_observability()
        self._messages, self._append_user, self._append_assistant = (
            messages,
            append_user,
            append_assistant,
        )

    @trace_method("agent_execution.repository.messages")
    async def messages(self) -> Sequence[ConversationMessage]:
        return await self._messages()

    @trace_method("agent_execution.repository.append_user")
    async def append_user(self, content: str, client_message_id: str | None = None) -> None:
        await self._append_user(content, client_message_id)

    @trace_method("agent_execution.repository.append_assistant")
    async def append_assistant(self, content: str) -> None:
        await self._append_assistant(content)


class InMemoryAgentExecutionRepository:
    """
    InMemoryAgentExecutionRepository is used for evaluations
    """

    def __init__(self, observability: Observability | None = None) -> None:
        self.observability = observability if observability is not None else get_observability()
        self._messages: list[ConversationMessage] = []

    @trace_method("agent_execution.repository.messages")
    async def messages(self) -> Sequence[ConversationMessage]:
        return tuple(self._messages)

    @trace_method("agent_execution.repository.append_user")
    async def append_user(self, content: str, client_message_id: str | None = None) -> None:
        self._messages.append(
            ConversationMessage(role="user", content=content, message_id=client_message_id)
        )

    @trace_method("agent_execution.repository.append_assistant")
    async def append_assistant(self, content: str) -> None:
        self._messages.append(ConversationMessage(role="assistant", content=content))
