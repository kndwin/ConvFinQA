from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import QueryableAttribute, selectinload
from sqlmodel import col

from src.module.chat_session_groups.chat_session_groups_repository_schema import (
    ChatSessionGroupRepositoryDeleteParams,
    ChatSessionGroupRepositoryGetByIdParams,
    ChatSessionGroupRepositoryGetParams,
    ChatSessionGroupRepositoryListParams,
    ChatSessionGroupRepositoryUpdateParams,
)
from src.platform.database.models import (
    ChatSessionGroupTable,
    ChatSessionTable,
    ChatSessionToGroupTable,
)
from src.platform.observability import trace_method
from src.platform.repository import BaseRepository


class ChatSessionGroupRepository(BaseRepository):
    async def _details(self, query):
        group = (await self.session.execute(query)).scalar_one_or_none()
        if group is None:
            return None
        result = await self.session.execute(
            select(ChatSessionTable)
            .join(
                ChatSessionToGroupTable,
                col(ChatSessionTable.id) == col(ChatSessionToGroupTable.chat_session_id),
            )
            .options(selectinload(cast(QueryableAttribute[Any], ChatSessionTable.tags)))
            .where(col(ChatSessionToGroupTable.chat_session_group_id) == group.id)
            .order_by(col(ChatSessionToGroupTable.position))
        )
        return group, list(result.scalars().all())

    @trace_method("chat_session_group.repository.list")
    async def list(self, params: ChatSessionGroupRepositoryListParams):
        result = await self.session.execute(
            select(ChatSessionGroupTable)
            .where(
                col(ChatSessionGroupTable.dataset_conversation_id) == params.dataset_conversation_id
            )
            .order_by(
                col(ChatSessionGroupTable.created_at).desc(), col(ChatSessionGroupTable.id).desc()
            )
        )
        groups = list(result.scalars().all())
        return [
            await self._details(
                select(ChatSessionGroupTable).where(col(ChatSessionGroupTable.id) == group.id)
            )
            for group in groups
        ]

    @trace_method("chat_session_group.repository.get")
    async def get(self, params: ChatSessionGroupRepositoryGetParams):
        return await self._details(
            select(ChatSessionGroupTable).where(
                col(ChatSessionGroupTable.id) == params.chat_session_group_id,
                col(ChatSessionGroupTable.dataset_conversation_id)
                == params.dataset_conversation_id,
            )
        )

    @trace_method("chat_session_group.repository.get_by_id")
    async def get_by_id(self, params: ChatSessionGroupRepositoryGetByIdParams):
        return await self._details(
            select(ChatSessionGroupTable).where(
                col(ChatSessionGroupTable.id) == params.chat_session_group_id
            )
        )

    @trace_method("chat_session_group.repository.update")
    async def update(self, params: ChatSessionGroupRepositoryUpdateParams):
        detail = await self.get(params)
        if detail is None:
            return None
        group, sessions = detail
        group.title = params.title
        group.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(group)
        return group, sessions

    @trace_method("chat_session_group.repository.delete")
    async def delete(self, params: ChatSessionGroupRepositoryDeleteParams) -> bool:
        detail = await self.get(params)
        if detail is None:
            return False
        group, sessions = detail
        if params.delete_chat_sessions:
            for session in sessions:
                await self.session.delete(session)
        else:
            await self.session.execute(
                delete(ChatSessionToGroupTable).where(
                    col(ChatSessionToGroupTable.chat_session_group_id) == group.id
                )
            )
        await self.session.delete(group)
        await self.session.commit()
        return True
