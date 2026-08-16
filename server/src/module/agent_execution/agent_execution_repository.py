from collections.abc import Sequence
from typing import Protocol

from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage


class AgentExecutionRepository(Protocol):
    async def messages(self) -> Sequence[ConversationMessage]: ...
    async def append_user(self, content: str, client_message_id: str | None = None) -> None: ...
    async def append_assistant(self, content: str) -> None: ...
