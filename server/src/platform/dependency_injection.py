import asyncio
from collections.abc import AsyncGenerator

from dishka import Provider, Scope, provide
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.module.chat_sessions.agent.calculator_mini_chat_agent import CalculatorMiniChatAgent
from src.module.chat_sessions.agent.direct_mini_chat_agent import DirectMiniChatAgent
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
    ) -> ChatSessionService:
        return ChatSessionService(
            chat_session_repository=chat_sessions_repository,
            dataset_conversation_repository=dataset_conversation_repository,
            observability=observability,
        )

    @provide(scope=Scope.REQUEST)
    def direct_mini_chat_agent(
        self,
        chat_sessions_repository: ChatSessionRepository,
        dataset_conversation_repository: DatasetConversationRepository,
        client: AsyncOpenAI | None,
        observability: Observability,
    ) -> DirectMiniChatAgent:
        return DirectMiniChatAgent(
            chat_session_repository=chat_sessions_repository,
            dataset_conversation_repository=dataset_conversation_repository,
            openai_client=client,
            observability=observability,
        )

    @provide(scope=Scope.REQUEST)
    def calculator_mini_chat_agent(
        self,
        chat_sessions_repository: ChatSessionRepository,
        dataset_conversation_repository: DatasetConversationRepository,
        client: AsyncOpenAI | None,
        observability: Observability,
    ) -> CalculatorMiniChatAgent:
        return CalculatorMiniChatAgent(
            chat_session_repository=chat_sessions_repository,
            dataset_conversation_repository=dataset_conversation_repository,
            openai_client=client,
            observability=observability,
        )
