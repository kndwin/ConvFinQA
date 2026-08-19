import builtins

from src.module.dataset_conversations.dataset_conversations_repository import (
    DatasetConversationRepository,
)
from src.module.dataset_conversations.dataset_conversations_service_schema import (
    DatasetConversationServiceGetParams,
    DatasetConversationServiceListParams,
)
from src.platform.database.models import DatasetConversationTable
from src.platform.observability import Observability, trace_method
from src.platform.service import BaseService


class DatasetConversationService(BaseService):
    def __init__(
        self,
        dataset_conversation_repository: DatasetConversationRepository,
        observability: Observability,
    ) -> None:
        super().__init__(observability)
        self.dataset_conversation_repository = dataset_conversation_repository

    @trace_method("dataset_conversation.service.get")
    async def get(
        self, params: DatasetConversationServiceGetParams
    ) -> DatasetConversationTable | None:
        return await self.dataset_conversation_repository.get(params)

    @trace_method("dataset_conversation.service.list")
    async def list(
        self, params: DatasetConversationServiceListParams
    ) -> builtins.list[DatasetConversationTable]:
        return await self.dataset_conversation_repository.list(params)
