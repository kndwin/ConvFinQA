import builtins

from sqlalchemy import select
from sqlmodel import col

from src.module.chat_session_tags.chat_session_tags_repository_schema import (
    ChatSessionTagRepositoryCreateParams,
    ChatSessionTagRepositoryGetParams,
    ChatSessionTagRepositoryListParams,
    ChatSessionTagRepositoryUpdateParams,
)
from src.platform.database.models import ChatSessionTagTable
from src.platform.observability import trace_method
from src.platform.repository import BaseRepository


class ChatSessionTagRepository(BaseRepository):
    @trace_method("chat_session_tag.repository.list")
    async def list(
        self, params: ChatSessionTagRepositoryListParams
    ) -> builtins.list[ChatSessionTagTable]:
        result = await self.session.execute(
            select(ChatSessionTagTable)
            .order_by(col(ChatSessionTagTable.id))
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(result.scalars().all())

    @trace_method("chat_session_tag.repository.get")
    async def get(self, params: ChatSessionTagRepositoryGetParams) -> ChatSessionTagTable | None:
        return await self.session.get(ChatSessionTagTable, params.chat_session_tag_id)

    @trace_method("chat_session_tag.repository.create")
    async def create(self, params: ChatSessionTagRepositoryCreateParams) -> ChatSessionTagTable:
        tag = ChatSessionTagTable(value=params.value)
        self.session.add(tag)
        try:
            await self.session.commit()
            await self.session.refresh(tag)
        except Exception:
            await self.session.rollback()
            raise
        return tag

    @trace_method("chat_session_tag.repository.update")
    async def update(
        self, params: ChatSessionTagRepositoryUpdateParams
    ) -> ChatSessionTagTable | None:
        tag = await self.get(
            ChatSessionTagRepositoryGetParams(chat_session_tag_id=params.chat_session_tag_id)
        )
        if tag is None:
            return None
        tag.value = params.value
        try:
            await self.session.commit()
            await self.session.refresh(tag)
        except Exception:
            await self.session.rollback()
            raise
        return tag

    @trace_method("chat_session_tag.repository.delete")
    async def delete(self, params: ChatSessionTagRepositoryGetParams) -> bool:
        tag = await self.get(params)
        if tag is None:
            return False
        await self.session.delete(tag)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return True
