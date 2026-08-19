import builtins

from sqlalchemy import select

from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryGetParams,
    DatasetConversationRepositoryListParams,
)
from src.platform.database.models import DatasetConversationTable
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
        result = await self.session.execute(statement)
        return list(result.scalars().all())
