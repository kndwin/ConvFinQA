import builtins
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import selectinload
from sqlmodel import col

from src.module.agent_execution.agent_execution_constants import (
    DEFAULT_CONTEXT_VERSION,
    DEFAULT_PROMPT_VERSIONS,
)
from src.module.chat_sessions.chat_sessions_repository_schema import (
    ChatSessionRepositoryCreateParams,
    ChatSessionRepositoryDeleteParams,
    ChatSessionRepositoryGetParams,
    ChatSessionRepositoryListParams,
    ChatSessionRepositoryPersistAssistantMessageParams,
    ChatSessionRepositoryPersistUserMessageParams,
    ChatSessionRepositoryUpdateParams,
)
from src.platform.database.models import (
    ChatMessageTable,
    ChatSessionTable,
    ChatSessionTagTable,
    ChatSessionToTagTable,
)
from src.platform.observability import trace_method
from src.platform.repository import BaseRepository


class ChatSessionRepository(BaseRepository):
    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @trace_method("chat_session.repository.list")
    async def list(
        self, params: ChatSessionRepositoryListParams
    ) -> builtins.list[ChatSessionTable]:
        result = await self.session.execute(
            select(ChatSessionTable)
            .options(selectinload(cast(Any, ChatSessionTable.tags)))
            .where(col(ChatSessionTable.dataset_conversation_id) == params.dataset_conversation_id)
            .order_by(col(ChatSessionTable.updated_at).desc(), col(ChatSessionTable.id).desc())
        )
        return list(result.scalars().all())

    @trace_method("chat_session.repository.get")
    async def get(self, params: ChatSessionRepositoryGetParams) -> ChatSessionTable | None:
        result = await self.session.execute(
            select(ChatSessionTable)
            .options(selectinload(cast(Any, ChatSessionTable.tags)))
            .where(
                col(ChatSessionTable.id) == params.chat_session_id,
                col(ChatSessionTable.dataset_conversation_id) == params.dataset_conversation_id,
            )
        )
        return result.scalar_one_or_none()

    @trace_method("chat_session.repository.messages")
    async def messages(
        self, params: ChatSessionRepositoryGetParams
    ) -> builtins.list[ChatMessageTable] | None:
        if await self.get(params) is None:
            return None
        result = await self.session.execute(
            select(ChatMessageTable)
            .where(col(ChatMessageTable.chat_session_id) == params.chat_session_id)
            .order_by(col(ChatMessageTable.created_at), col(ChatMessageTable.id))
        )
        return list(result.scalars().all())

    @trace_method("chat_session.repository.persist_user_message")
    async def persist_user_message(
        self,
        chat_session: ChatSessionTable,
        params: ChatSessionRepositoryPersistUserMessageParams,
    ) -> None:
        # AG-UI reconnects resend the same client message.  Do the lookup in
        # addition to the database constraint so this also works on SQLite.
        if params.client_message_id is not None:
            existing = await self.session.execute(
                select(ChatMessageTable).where(
                    col(ChatMessageTable.chat_session_id) == params.chat_session_id,
                    col(ChatMessageTable.client_message_id) == params.client_message_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                return
        self.session.add(
            ChatMessageTable(
                chat_session_id=params.chat_session_id,
                role="user",
                content=params.content,
                client_message_id=params.client_message_id,
            )
        )
        chat_session.updated_at = datetime.now(UTC)
        if not chat_session.title:
            chat_session.title = params.content[:60]
        await self._commit()

    @trace_method("chat_session.repository.persist_assistant_message")
    async def persist_assistant_message(
        self,
        chat_session: ChatSessionTable,
        params: ChatSessionRepositoryPersistAssistantMessageParams,
    ) -> None:
        self.session.add(
            ChatMessageTable(
                chat_session_id=params.chat_session_id,
                role="assistant",
                content=params.content,
            )
        )
        chat_session.updated_at = datetime.now(UTC)
        await self._commit()

    @trace_method("chat_session.repository.create")
    async def create(
        self, params: ChatSessionRepositoryCreateParams, *, commit: bool = True
    ) -> ChatSessionTable:
        chat_session = ChatSessionTable(
            dataset_conversation_id=params.dataset_conversation_id,
            agent_approach=str(params.agent_approach),
            prompt_version=(DEFAULT_PROMPT_VERSIONS[params.agent_approach]),
            context_version=DEFAULT_CONTEXT_VERSION,
            model=str(params.model),
        )
        self.session.add(chat_session)
        try:
            # Group creation can defer the transaction commit, but the session must
            # still be persistent before it can be refreshed or referenced by a
            # membership row. Tags also need the generated session ID.
            if params.tags or not commit:
                await self.session.flush()
            if params.tags:
                values = [tag.value for tag in params.tags]
                await self.session.execute(
                    postgres_insert(ChatSessionTagTable)
                    .values([{"value": value} for value in values])
                    .on_conflict_do_nothing(index_elements=["value"])
                )
                result = await self.session.execute(
                    select(ChatSessionTagTable).where(col(ChatSessionTagTable.value).in_(values))
                )
                tags_by_value = {tag.value: tag for tag in result.scalars().all()}
                await self.session.flush()
                assert chat_session.id is not None
                assert all(tag.id is not None for tag in tags_by_value.values())
                for tag in tags_by_value.values():
                    self.session.add(
                        ChatSessionToTagTable(
                            chat_session_id=chat_session.id, tag_id=cast(int, tag.id)
                        )
                    )
            if commit:
                await self.session.commit()
            await self.session.refresh(chat_session)
            # Response serialization must never trigger async relationship I/O.
            # Load the (possibly empty) tag collection before leaving the repository.
            result = await self.session.execute(
                select(ChatSessionTable)
                .options(selectinload(cast(Any, ChatSessionTable.tags)))
                .where(col(ChatSessionTable.id) == chat_session.id)
            )
            loaded = result.scalar_one_or_none()
            if loaded is None:
                raise RuntimeError("created chat session could not be reloaded")
            return loaded
        except Exception:
            if commit:
                await self.session.rollback()
            raise

    @trace_method("chat_session.repository.update")
    async def update(self, params: ChatSessionRepositoryUpdateParams) -> ChatSessionTable | None:
        chat_session = await self.get(
            ChatSessionRepositoryGetParams(
                dataset_conversation_id=params.dataset_conversation_id,
                chat_session_id=params.chat_session_id,
            )
        )
        if chat_session is None:
            return None
        if params.title_provided:
            chat_session.title = params.title
        chat_session.updated_at = datetime.now(UTC)
        try:
            if params.tags_provided:
                values = [tag.value for tag in (params.tags or [])]
                if values:
                    await self.session.execute(
                        postgres_insert(ChatSessionTagTable)
                        .values([{"value": value} for value in values])
                        .on_conflict_do_nothing(index_elements=["value"])
                    )
                    result = await self.session.execute(
                        select(ChatSessionTagTable).where(col(ChatSessionTagTable.value).in_(values))
                    )
                    tags_by_value = {tag.value: tag for tag in result.scalars().all()}
                    await self.session.flush()
                else:
                    tags_by_value = {}
                await self.session.execute(
                    delete(ChatSessionToTagTable).where(
                        ChatSessionToTagTable.chat_session_id == chat_session.id
                    )
                )
                for tag in tags_by_value.values():
                    self.session.add(
                        ChatSessionToTagTable(
                            chat_session_id=chat_session.id, tag_id=cast(int, tag.id)
                        )
                    )
            await self.session.commit()
            result = await self.session.execute(
                select(ChatSessionTable)
                .options(selectinload(cast(Any, ChatSessionTable.tags)))
                .where(col(ChatSessionTable.id) == chat_session.id)
            )
            chat_session = result.scalar_one()
        except Exception:
            await self.session.rollback()
            raise
        return chat_session

    @trace_method("chat_session.repository.delete")
    async def delete(self, params: ChatSessionRepositoryDeleteParams) -> bool:
        chat_session = await self.get(
            ChatSessionRepositoryGetParams(
                dataset_conversation_id=params.dataset_conversation_id,
                chat_session_id=params.chat_session_id,
            )
        )
        if chat_session is None:
            return False
        await self.session.delete(chat_session)
        await self.session.commit()
        return True
