"""Durable, idempotent adapter used by the ensemble workflow."""

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlmodel import col
from temporalio import activity

from src.module.agent_execution.execution.durable.ensemble_workflow_schema import (
    EnsembleFailureFinalizationInput,
    EnsembleFinalizationInput,
)
from src.platform.database.database import session_factory
from src.platform.database.models import AgentRunTable, ChatMessageTable


@activity.defn(name="finalize-ensemble-run")
async def finalize_ensemble_run(request: EnsembleFinalizationInput) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(AgentRunTable).where(
                col(AgentRunTable.run_id) == request.target.run_id,
                col(AgentRunTable.chat_session_id) == request.target.chat_session_id,
                col(AgentRunTable.temporal_workflow_id) == request.target.workflow_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None or run.status == "completed":
            return
        output = request.output
        message = ChatMessageTable(
            chat_session_id=run.chat_session_id,
            role="assistant",
            content=output.reviewer_output,
            client_message_id=f"ensemble-assistant:{request.target.run_id}",
        )
        session.add(message)
        await session.flush()
        run.assistant_message_id = message.id
        run.status = "completed"
        run.error = None
        run.diagnostics_json = json.dumps(
            {
                "candidates": [item.model_dump() for item in output.candidates],
                "reviewer_prompt_version": output.reviewer_prompt_version,
            }
        )
        run.completed_at = datetime.now(UTC)
        await session.commit()


@activity.defn(name="fail-ensemble-run")
async def fail_ensemble_run(request: EnsembleFailureFinalizationInput) -> None:
    """Persist a sanitized terminal failure without creating an assistant message."""
    async with session_factory() as session:
        result = await session.execute(
            select(AgentRunTable).where(
                col(AgentRunTable.run_id) == request.target.run_id,
                col(AgentRunTable.chat_session_id) == request.target.chat_session_id,
                col(AgentRunTable.temporal_workflow_id) == request.target.workflow_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None or run.status in {"completed", "failed", "cancelled"}:
            return
        run.status = "failed"
        run.error = request.error
        run.completed_at = datetime.now(UTC)
        await session.commit()
