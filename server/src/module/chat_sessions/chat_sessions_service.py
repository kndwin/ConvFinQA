import builtins

from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
from src.module.chat_sessions.chat_sessions_service_schema import (
    ChatSessionServiceCreateParams,
    ChatSessionServiceDeleteParams,
    ChatSessionServiceGetParams,
    ChatSessionServiceListParams,
    ChatSessionServiceUpdateParams,
)
from src.module.dataset_conversations.dataset_conversations_repository import (
    DatasetConversationRepository,
)
from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryGetParams,
)
from src.platform.database.models import ChatMessageTable, ChatSessionTable
from src.platform.observability import Observability, trace_method
from src.platform.service import BaseService


class ChatSessionService(BaseService):
    def __init__(
        self,
        chat_session_repository: ChatSessionRepository,
        dataset_conversation_repository: DatasetConversationRepository,
        observability: Observability,
    ) -> None:
        super().__init__(observability)
        self.chat_session_repository = chat_session_repository
        self.dataset_conversation_repository = dataset_conversation_repository

    @trace_method("chat_session.service.list")
    async def list(self, params: ChatSessionServiceListParams) -> builtins.list[ChatSessionTable]:
        return await self.chat_session_repository.list(params)

    @trace_method("chat_session.service.get")
    async def get(self, params: ChatSessionServiceGetParams) -> ChatSessionTable | None:
        return await self.chat_session_repository.get(params)

    @trace_method("chat_session.service.messages")
    async def messages(
        self, params: ChatSessionServiceGetParams
    ) -> builtins.list[ChatMessageTable] | None:
        return await self.chat_session_repository.messages(params)

    @trace_method("chat_session.service.create")
    async def create(self, params: ChatSessionServiceCreateParams) -> ChatSessionTable | None:
        parent = await self.dataset_conversation_repository.get(
            DatasetConversationRepositoryGetParams(
                dataset_conversation_id=params.dataset_conversation_id
            )
        )
        return await self.chat_session_repository.create(params) if parent else None

    @trace_method("chat_session.service.update")
    async def update(self, params: ChatSessionServiceUpdateParams) -> ChatSessionTable | None:
        return await self.chat_session_repository.update(params)

    @trace_method("chat_session.service.delete")
    async def delete(self, params: ChatSessionServiceDeleteParams) -> bool:
        return await self.chat_session_repository.delete(params)
