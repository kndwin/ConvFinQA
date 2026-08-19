import builtins
import json
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import selectinload
from sqlmodel import col

from src.module.agent_execution.agent_approach.ensemble.definition import (
    build_pinned_ensemble_config,
)
from src.module.agent_execution.agent_execution_constants import (
    DEFAULT_CONTEXT_VERSION,
    DEFAULT_PROMPT_VERSIONS,
    REVIEWER_PROMPT_VERSION,
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
    AgentRunTable,
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

    async def prepare_run(
        self, chat_session_id: int, run_id: str, model: str, workflow_id: str
    ) -> AgentRunTable:
        """Get-or-create a durable run, rejecting a globally colliding run id."""
        result = await self.session.execute(
            select(AgentRunTable).where(col(AgentRunTable.run_id) == run_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.chat_session_id != chat_session_id:
                raise ValueError("run does not belong to this chat session") from None
            return existing
        row = AgentRunTable(
            run_id=run_id,
            chat_session_id=chat_session_id,
            status="running",
            model=model,
            temporal_workflow_id=workflow_id,
            started_at=datetime.now(UTC),
        )
        self.session.add(row)
        try:
            await self.session.commit()
            await self.session.refresh(row)
        except Exception:
            await self.session.rollback()
            result = await self.session.execute(
                select(AgentRunTable).where(col(AgentRunTable.run_id) == run_id)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                raise
            if existing.chat_session_id != chat_session_id:
                raise ValueError("run does not belong to this chat session") from None
            return existing
        return row

    async def get_run(self, chat_session_id: int, run_id: str) -> AgentRunTable | None:
        result = await self.session.execute(
            select(AgentRunTable).where(
                col(AgentRunTable.chat_session_id) == chat_session_id,
                col(AgentRunTable.run_id) == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_run_cancelled(self, chat_session_id: int, run_id: str) -> None:
        run = await self.get_run(chat_session_id, run_id)
        if run is None or run.status in {"completed", "failed", "cancelled"}:
            return
        run.status = "cancelled"
        run.error = "cancelled by client"
        run.completed_at = datetime.now(UTC)
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
        ensemble_config = None
        if params.agent_approach.value == "ensemble":
            ensemble_config = build_pinned_ensemble_config(
                params.ensemble_candidates or ()
            ).model_dump(mode="json")
        chat_session = ChatSessionTable(
            dataset_conversation_id=params.dataset_conversation_id,
            agent_approach=str(params.agent_approach),
            prompt_version=(
                REVIEWER_PROMPT_VERSION
                if params.agent_approach.value == "ensemble"
                else DEFAULT_PROMPT_VERSIONS[params.agent_approach]
            ),
            context_version=DEFAULT_CONTEXT_VERSION,
            model=str(params.model),
            ensemble_config_json=json.dumps(ensemble_config)
            if ensemble_config is not None
            else None,
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
        chat_session.title = params.title
        chat_session.updated_at = datetime.now(UTC)
        try:
            await self.session.commit()
            await self.session.refresh(chat_session)
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
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return True
