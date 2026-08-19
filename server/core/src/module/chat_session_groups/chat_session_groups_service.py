import builtins

from src.module.chat_session_groups.chat_session_groups_repository import ChatSessionGroupRepository
from src.module.chat_session_groups.chat_session_groups_repository_schema import (
    ChatSessionGroupRepositoryGetParams,
)
from src.module.chat_session_groups.chat_session_groups_service_schema import (
    ChatSessionGroupServiceCreateParams,
    ChatSessionGroupServiceDeleteParams,
    ChatSessionGroupServiceGetByIdParams,
    ChatSessionGroupServiceGetParams,
    ChatSessionGroupServiceListParams,
    ChatSessionGroupServiceUpdateParams,
)
from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
from src.module.chat_sessions.chat_sessions_repository_schema import (
    ChatSessionRepositoryCreateParams,
)
from src.module.dataset_conversations.dataset_conversations_repository import (
    DatasetConversationRepository,
)
from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryGetParams,
)
from src.platform.database.models import (
    ChatSessionGroupTable,
    ChatSessionTable,
    ChatSessionToGroupTable,
)
from src.platform.observability import Observability
from src.platform.service import BaseService


class ChatSessionGroupService(BaseService):
    def __init__(
        self,
        repository: ChatSessionGroupRepository,
        chat_sessions: ChatSessionRepository,
        dataset_conversations: DatasetConversationRepository,
        observability: Observability,
    ) -> None:
        super().__init__(observability)
        self.repository = repository
        self.chat_sessions = chat_sessions
        self.dataset_conversations = dataset_conversations

    async def list(
        self, params: ChatSessionGroupServiceListParams
    ) -> builtins.list[tuple[ChatSessionGroupTable, builtins.list[ChatSessionTable]]]:
        return await self.repository.list(params)

    async def get(
        self, params: ChatSessionGroupServiceGetParams
    ) -> tuple[ChatSessionGroupTable, builtins.list[ChatSessionTable]] | None:
        return await self.repository.get(params)

    async def get_by_id(
        self, params: ChatSessionGroupServiceGetByIdParams
    ) -> tuple[ChatSessionGroupTable, builtins.list[ChatSessionTable]] | None:
        return await self.repository.get_by_id(params)

    async def update(
        self, params: ChatSessionGroupServiceUpdateParams
    ) -> tuple[ChatSessionGroupTable, builtins.list[ChatSessionTable]] | None:
        return await self.repository.update(params)

    async def delete(self, params: ChatSessionGroupServiceDeleteParams) -> bool:
        return await self.repository.delete(params)

    async def create(
        self, params: ChatSessionGroupServiceCreateParams
    ) -> tuple[ChatSessionGroupTable, builtins.list[ChatSessionTable]] | None:
        if (
            await self.dataset_conversations.get(
                DatasetConversationRepositoryGetParams(
                    dataset_conversation_id=params.dataset_conversation_id
                )
            )
            is None
        ):
            return None
        group = ChatSessionGroupTable(
            dataset_conversation_id=params.dataset_conversation_id, title=params.title
        )
        self.repository.session.add(group)
        try:
            await self.repository.session.flush()
            assert group.id is not None
            sessions = []
            for position, config in enumerate(params.configs):
                session = await self.chat_sessions.create(
                    ChatSessionRepositoryCreateParams(
                        dataset_conversation_id=params.dataset_conversation_id,
                        agent_approach=config.agent_approach,
                        model=config.model,
                        ensemble_candidates=config.ensemble_candidates,
                        tags=config.tags,
                    ),
                    commit=False,
                )
                assert session.id is not None
                sessions.append(session)
                self.repository.session.add(
                    ChatSessionToGroupTable(
                        chat_session_group_id=group.id,
                        chat_session_id=session.id,
                        position=position,
                    )
                )
            await self.repository.session.commit()
            return await self.repository.get(
                ChatSessionGroupRepositoryGetParams(
                    dataset_conversation_id=params.dataset_conversation_id,
                    chat_session_group_id=group.id,
                )
            )
        except Exception:
            await self.repository.session.rollback()
            raise
