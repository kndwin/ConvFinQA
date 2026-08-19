import builtins

from src.module.chat_session_tags.chat_session_tags_repository import ChatSessionTagRepository
from src.module.chat_session_tags.chat_session_tags_service_schema import (
    ChatSessionTagServiceCreateParams,
    ChatSessionTagServiceGetParams,
    ChatSessionTagServiceListParams,
    ChatSessionTagServiceUpdateParams,
)
from src.platform.database.models import ChatSessionTagTable
from src.platform.observability import Observability, trace_method
from src.platform.service import BaseService


class ChatSessionTagService(BaseService):
    def __init__(
        self,
        chat_session_tag_repository: ChatSessionTagRepository,
        observability: Observability,
    ):
        super().__init__(observability)
        self.chat_session_tag_repository = chat_session_tag_repository

    @trace_method("chat_session_tag.service.list")
    async def list(
        self, params: ChatSessionTagServiceListParams
    ) -> builtins.list[ChatSessionTagTable]:
        return await self.chat_session_tag_repository.list(params)

    @trace_method("chat_session_tag.service.get")
    async def get(self, params: ChatSessionTagServiceGetParams) -> ChatSessionTagTable | None:
        return await self.chat_session_tag_repository.get(params)

    @trace_method("chat_session_tag.service.create")
    async def create(self, params: ChatSessionTagServiceCreateParams) -> ChatSessionTagTable:
        return await self.chat_session_tag_repository.create(params)

    @trace_method("chat_session_tag.service.update")
    async def update(self, params: ChatSessionTagServiceUpdateParams) -> ChatSessionTagTable | None:
        return await self.chat_session_tag_repository.update(params)

    @trace_method("chat_session_tag.service.delete")
    async def delete(self, params: ChatSessionTagServiceGetParams) -> bool:
        return await self.chat_session_tag_repository.delete(params)
