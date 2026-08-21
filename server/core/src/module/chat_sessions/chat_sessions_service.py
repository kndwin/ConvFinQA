import builtins
from collections.abc import AsyncIterator

from ag_ui.core import BaseEvent, RunAgentInput, RunErrorEvent

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.agent_execution.agent_execution_repository import CallbackAgentExecutionRepository
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_service import AgentExecutionService
from src.module.agent_execution.agent_execution_service_schema import AgentExecutionServiceRunParams
from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
from src.module.chat_sessions.chat_sessions_repository_schema import (
    ChatSessionRepositoryGetParams,
    ChatSessionRepositoryPersistAssistantMessageParams,
    ChatSessionRepositoryPersistUserMessageParams,
)
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
        agent_execution_service: AgentExecutionService,
    ) -> None:
        super().__init__(observability)
        self.chat_session_repository = chat_session_repository
        self.dataset_conversation_repository = dataset_conversation_repository
        self.agent_execution_service = agent_execution_service

    @trace_method("chat_session.service.run")
    async def run(
        self, dataset_conversation_id: int, chat_session_id: int, input_data: RunAgentInput
    ) -> AsyncIterator[BaseEvent]:
        session = await self.chat_session_repository.get(
            ChatSessionRepositoryGetParams(
                dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
            )
        )
        dataset = await self.dataset_conversation_repository.get(
            DatasetConversationRepositoryGetParams(dataset_conversation_id=dataset_conversation_id)
        )
        if session is None or dataset is None:
            yield RunErrorEvent(message="Chat session not found", code="not_found")
            return

        async def messages() -> tuple[ConversationMessage, ...]:
            rows = await self.chat_session_repository.messages(
                ChatSessionRepositoryGetParams(
                    dataset_conversation_id=dataset_conversation_id, chat_session_id=chat_session_id
                )
            )
            return tuple(
                ConversationMessage(
                    role=row.role,
                    content=row.content,
                    message_id=str(row.id) if row.id is not None else None,
                )
                for row in (rows or [])
                if row.role in {"user", "assistant"} and row.content.strip()
            )

        async def append_user(content: str, client_message_id: str | None) -> None:
            await self.chat_session_repository.persist_user_message(
                session,
                ChatSessionRepositoryPersistUserMessageParams(
                    chat_session_id=chat_session_id,
                    content=content,
                    client_message_id=client_message_id,
                ),
            )

        async def append_assistant(content: str) -> None:
            await self.chat_session_repository.persist_assistant_message(
                session,
                ChatSessionRepositoryPersistAssistantMessageParams(
                    chat_session_id=chat_session_id, content=content
                ),
            )

        repository = CallbackAgentExecutionRepository(
            messages, append_user, append_assistant, observability=self.observability
        )
        try:
            approach = AgentApproach(session.agent_approach)
        except ValueError:
            yield RunErrorEvent(message="Unsupported agent approach", code="run_error")
            return
        try:
            model = OpenAIModel(session.model)
        except ValueError:
            yield RunErrorEvent(message="Unsupported agent model", code="run_error")
            return
        params = AgentExecutionServiceRunParams(
            approach=approach,
            prompt_version=session.prompt_version,
            context_version=session.context_version,
            model=model,
            document=dataset.doc_json or "",
            input_data=input_data,
            trace_metadata={
                "dataset_conversation_id": str(dataset_conversation_id),
                "chat_session_id": str(chat_session_id),
                "ag_ui_run_id": input_data.run_id,
            },
        )
        async for event in self.agent_execution_service.run(params, repository):
            yield event

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
