import builtins

from sqlalchemy import exists, select

from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryGetParams,
    DatasetConversationRepositoryListParams,
)
from src.platform.database.models import (
    ChatSessionTable,
    ChatSessionTagTable,
    ChatSessionToTagTable,
    DatasetConversationTable,
)
from src.platform.observability import trace_method
from src.platform.repository import BaseRepository


class DatasetConversationRepository(BaseRepository):
    @trace_method("dataset_conversation.repository.get")
    async def get(
        self, params: DatasetConversationRepositoryGetParams
    ) -> DatasetConversationTable | None:
        return await self.session.get(DatasetConversationTable, params.dataset_conversation_id)

    @trace_method("dataset_conversation.repository.list")
    async def list(
        self, params: DatasetConversationRepositoryListParams
    ) -> builtins.list[DatasetConversationTable]:
        statement = (
            select(DatasetConversationTable)
            .order_by(DatasetConversationTable.id)  # ty: ignore[invalid-argument-type]
            .offset(params.offset)
            .limit(params.limit)
        )
        if params.tags:
            tagged_session = (
                select(1)
                .select_from(ChatSessionTable)
                .join(
                    ChatSessionToTagTable,
                    ChatSessionToTagTable.chat_session_id == ChatSessionTable.id,
                )
                .join(ChatSessionTagTable, ChatSessionTagTable.id == ChatSessionToTagTable.tag_id)
                .where(
                    ChatSessionTable.dataset_conversation_id == DatasetConversationTable.id,
                    ChatSessionTagTable.value.in_(params.tags),
                )
            )
            statement = statement.where(exists(tagged_session))
        result = await self.session.execute(statement)
        return list(result.scalars().all())
