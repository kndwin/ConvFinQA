import asyncio
from collections.abc import AsyncGenerator

from dishka import Provider, Scope, provide
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.module.agent_execution.agent_execution_service import AgentExecutionService
from src.module.chat_session_groups.chat_session_groups_repository import ChatSessionGroupRepository
from src.module.chat_session_groups.chat_session_groups_service import ChatSessionGroupService
from src.module.chat_session_tags.chat_session_tags_repository import ChatSessionTagRepository
from src.module.chat_session_tags.chat_session_tags_service import ChatSessionTagService
from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
from src.module.chat_sessions.chat_sessions_service import ChatSessionService
from src.module.dataset_conversations.dataset_conversations_repository import (
    DatasetConversationRepository,
)
from src.module.dataset_conversations.dataset_conversations_service import (
    DatasetConversationService,
)
from src.platform.database.database import session_factory
from src.platform.observability import Observability, get_observability
from src.platform.openai import openai_client as provide_openai_client


class ApplicationProvider(Provider):
    """Construct application objects at their intended lifetime."""

    @provide(scope=Scope.APP)
    def observability(self) -> Observability:
        return get_observability()

    @provide(scope=Scope.APP)
    async def openai_client(self) -> AsyncGenerator[AsyncOpenAI | None]:
        async with provide_openai_client() as client:
            yield client

    @provide(scope=Scope.REQUEST)
    async def session(self) -> AsyncGenerator[AsyncSession, BaseException | None]:
        async with session_factory() as session:
            exception = yield session
            if exception is not None:
                await asyncio.shield(session.rollback())

    @provide(scope=Scope.REQUEST)
    def dataset_conversation_repository(
        self, session: AsyncSession, observability: Observability
    ) -> DatasetConversationRepository:
        return DatasetConversationRepository(session, observability)

    @provide(scope=Scope.REQUEST)
    def dataset_conversation_service(
        self,
        dataset_conversation_repository: DatasetConversationRepository,
        observability: Observability,
    ) -> DatasetConversationService:
        return DatasetConversationService(
            dataset_conversation_repository=dataset_conversation_repository,
            observability=observability,
        )

    @provide(scope=Scope.REQUEST)
    def chat_session_tag_repository(
        self, session: AsyncSession, observability: Observability
    ) -> ChatSessionTagRepository:
        return ChatSessionTagRepository(session, observability)

    @provide(scope=Scope.REQUEST)
    def chat_session_tag_service(
        self, chat_session_tag_repository: ChatSessionTagRepository, observability: Observability
    ) -> ChatSessionTagService:
        return ChatSessionTagService(chat_session_tag_repository, observability)

    @provide(scope=Scope.REQUEST)
    def chat_sessions_repository(
        self, session: AsyncSession, observability: Observability
    ) -> ChatSessionRepository:
        return ChatSessionRepository(session, observability)

    @provide(scope=Scope.REQUEST)
    def chat_sessions_service(
        self,
        chat_sessions_repository: ChatSessionRepository,
        dataset_conversation_repository: DatasetConversationRepository,
        observability: Observability,
        agent_execution_service: AgentExecutionService,
    ) -> ChatSessionService:
        return ChatSessionService(
            chat_session_repository=chat_sessions_repository,
            dataset_conversation_repository=dataset_conversation_repository,
            observability=observability,
            agent_execution_service=agent_execution_service,
        )

    @provide(scope=Scope.REQUEST)
    def chat_session_group_repository(
        self, session: AsyncSession, observability: Observability
    ) -> ChatSessionGroupRepository:
        return ChatSessionGroupRepository(session, observability)

    @provide(scope=Scope.REQUEST)
    def chat_session_group_service(
        self,
        chat_session_group_repository: ChatSessionGroupRepository,
        chat_sessions_repository: ChatSessionRepository,
        dataset_conversation_repository: DatasetConversationRepository,
        observability: Observability,
    ) -> ChatSessionGroupService:
        return ChatSessionGroupService(
            chat_session_group_repository,
            chat_sessions_repository,
            dataset_conversation_repository,
            observability,
        )

    @provide(scope=Scope.APP)
    def agent_execution_service(self, client: AsyncOpenAI | None) -> AgentExecutionService:
        return AgentExecutionService(client)
