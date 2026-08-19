import asyncio
import base64
import binascii
import json
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

from ag_ui.core import (
    CustomEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)

from src.module.agent_execution.agent_approach.ensemble.prompts.reviewer import (
    resolve as resolve_reviewer,
)
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_preparation import AgentExecutionPreparationService
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_service import AgentExecutionService
from src.module.agent_execution.agent_execution_util import newest_user_message
from src.module.agent_execution.execution.durable.durable_execution_backend import (
    DurableExecutionBackend,
)
from src.module.agent_execution.execution.durable.ensemble_workflow import EnsembleWorkflow
from src.module.agent_execution.execution.durable.ensemble_workflow_schema import (
    EnsembleCandidateInput,
    EnsembleFinalizationTarget,
    EnsembleWorkflowInput,
)
from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
from src.module.chat_sessions.chat_sessions_repository_schema import (
    ChatSessionRepositoryGetParams,
    ChatSessionRepositoryPersistUserMessageParams,
)
from src.module.dataset_conversations.dataset_conversations_repository import (
    DatasetConversationRepository,
)
from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryGetParams,
)
from src.platform.config import config


class ChatSessionRunAdapter:
    def __init__(
        self,
        repository: ChatSessionRepository,
        datasets: DatasetConversationRepository,
        approaches: AgentExecutionService | None,
        backend: DurableExecutionBackend,
    ) -> None:
        self.repository, self.datasets, self.approaches = repository, datasets, approaches
        # Some stream-only callers construct this adapter with no approach
        # service; preparation is only needed by prepare_start.
        self.preparation = (
            AgentExecutionPreparationService(self.approaches.resolve_approach)
            if self.approaches is not None
            else None
        )
        self.backend = backend

    async def prepare_start(self, dataset_id: int, chat_id: int, data: RunAgentInput) -> str:
        session = await self.repository.get(
            ChatSessionRepositoryGetParams(
                dataset_conversation_id=dataset_id, chat_session_id=chat_id
            )
        )
        dataset = await self.datasets.get(
            DatasetConversationRepositoryGetParams(dataset_conversation_id=dataset_id)
        )
        if session is None or dataset is None:
            raise LookupError("chat session not found")
        selected = newest_user_message(data)
        if selected is None:
            raise ValueError("A user message is required")
        question, client_message_id = selected
        workflow_id = f"ensemble:{chat_id}:{data.run_id}"
        prior_rows = (
            await self.repository.messages(
                ChatSessionRepositoryGetParams(
                    dataset_conversation_id=dataset_id, chat_session_id=chat_id
                )
            )
            or []
        )
        prior = tuple(
            ConversationMessage(
                role=row.role,
                content=row.content,
                message_id=str(row.id) if row.id is not None else None,
            )
            for row in (prior_rows or [])
            if row.role in {"user", "assistant"} and row.content.strip()
        )
        cfg = json.loads(session.ensemble_config_json or "{}")
        if self.preparation is None:
            raise RuntimeError("Agent approach preparation is not configured")
        candidates = []
        for item in cfg.get("candidates", []):
            approach = AgentApproach(item["approach"])
            prepared = self.preparation.prepare(
                approach,
                name=str(approach),
                prompt_version=item["prompt_version"],
                context_version=item["context_version"],
                document=dataset.doc_json or "",
                transcript=prior,
                question=question,
                model=str(session.model),
                expected_prompt_hash=item.get("prompt_hash"),
                expected_context_hash=item.get("context_hash"),
            )
            candidates.append(
                EnsembleCandidateInput(
                    approach=str(prepared.approach),
                    name=prepared.name,
                    instructions=prepared.instructions,
                    rendered_context=prepared.rendered_context,
                    model=prepared.model,
                    prompt_version=prepared.prompt_version,
                    prompt_hash=prepared.prompt_hash,
                    context_version=prepared.context_version,
                    context_hash=prepared.context_hash,
                    trace_metadata={
                        "chat_session_id": str(chat_id),
                        "ag_ui_run_id": data.run_id,
                        "prompt_version": prepared.prompt_version,
                        "context_version": prepared.context_version,
                    },
                )
            )
        reviewer = resolve_reviewer(cfg.get("reviewer_prompt_version", "ensemble-reviewer:v1"))
        expected_reviewer_hash = cfg.get("reviewer_prompt_hash")
        if expected_reviewer_hash and expected_reviewer_hash != reviewer.content_hash:
            raise ValueError(
                "Persisted ensemble reviewer prompt hash does not match the resolved prompt"
            )
        request = EnsembleWorkflowInput(
            question=question,
            context=dataset.doc_json or "",
            candidates=tuple(candidates),
            reviewer_instructions=reviewer.instructions,
            reviewer_model=session.model,
            trace_metadata={"chat_session_id": str(chat_id), "ag_ui_run_id": data.run_id},
            finalization=EnsembleFinalizationTarget(
                run_id=data.run_id, chat_session_id=chat_id, workflow_id=workflow_id
            ),
        )
        # Nothing is persisted until every immutable prompt/context pin has been
        # resolved and verified.  In particular, a bad pin must not create a
        # misleading running row.
        await self.backend.preflight()
        await self.repository.persist_user_message(
            session,
            ChatSessionRepositoryPersistUserMessageParams(
                chat_session_id=chat_id,
                content=question,
                client_message_id=client_message_id,
            ),
        )
        await self.repository.prepare_run(chat_id, data.run_id, session.model, workflow_id)
        await self.backend.start_workflow(
            EnsembleWorkflow.run,
            request,
            workflow_id,
            config.temporal_task_queue,
            timedelta(seconds=config.temporal_ensemble_execution_timeout_seconds),
        )
        return workflow_id

    async def run_events(
        self, dataset_id: int, chat_id: int, data: RunAgentInput
    ) -> AsyncIterator[Any]:
        workflow_id = await self.prepare_start(dataset_id, chat_id, data)
        candidates = await self.candidate_names(dataset_id, chat_id)
        async for event in self.stream_events(workflow_id, data.thread_id, data.run_id, candidates):
            yield event

    async def candidate_names(self, dataset_id: int, chat_id: int) -> tuple[str, ...]:
        session = await self.repository.get(
            ChatSessionRepositoryGetParams(
                dataset_conversation_id=dataset_id, chat_session_id=chat_id
            )
        )
        if session is None:
            raise LookupError("chat session not found")
        cfg = json.loads(session.ensemble_config_json or "{}")
        return tuple(str(item["approach"]) for item in cfg.get("candidates", []))

    @staticmethod
    def decode_cursor(value: str | None, sources: set[str]) -> dict[str, int]:
        """Decode the deliberately opaque, bounded replay cursor."""
        if not value:
            return {}
        if len(value) > 4096:
            return {}
        try:
            raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
            decoded = json.loads(raw)
            if not isinstance(decoded, dict) or set(decoded) - sources:
                return {}
            return {
                key: offset
                for key, offset in decoded.items()
                if isinstance(key, str)
                and isinstance(offset, int)
                and not isinstance(offset, bool)
                and 0 <= offset <= 2**63 - 1
            }
        except ValueError, TypeError, json.JSONDecodeError, binascii.Error:
            return {}

    @staticmethod
    def encode_cursor(offsets: dict[str, int]) -> str:
        payload = json.dumps(offsets, sort_keys=True, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def raw_text_delta(raw: Any) -> str | None:
        """Extract only the portable OpenAI Responses text-delta event."""
        kind = raw.get("type") if isinstance(raw, dict) else getattr(raw, "type", None)
        if str(kind) != "response.output_text.delta":
            return None
        delta = raw.get("delta") if isinstance(raw, dict) else getattr(raw, "delta", None)
        return delta if isinstance(delta, str) else None

    async def stream_events(
        self,
        workflow_id: str,
        thread_id: str,
        run_id: str,
        candidates: tuple[str, ...],
        cursor: dict[str, int] | None = None,
    ) -> AsyncIterator[Any]:
        yield RunStartedEvent(thread_id=thread_id, run_id=run_id)
        await self.backend.preflight()
        sources = {f"candidate:{name}" for name in candidates} | {"reviewer"}
        offsets = {key: 0 for key in sources}
        offsets.update(cursor or {})
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        workflow_ids = {
            key: workflow_id if key == "reviewer" else f"{workflow_id}:{key}" for key in sources
        }
        # Use the typed handle for the parent result. A handle created only
        # from an ID has no return annotation and therefore decodes the
        # result as a plain dict.
        reviewer_handle = await self.backend.typed_handle(EnsembleWorkflow.run, workflow_id)

        async def consume(key: str, source_id: str) -> None:
            try:
                async for item in self.backend.subscribe(
                    source_id, config.temporal_streaming_topic, offsets[key]
                ):
                    await queue.put((key, item))
            except asyncio.CancelledError:
                raise
            except Exception:
                return

        subscribers = [
            asyncio.create_task(consume(key, source_id)) for key, source_id in workflow_ids.items()
        ]
        # Temporal's default converter returns a dict when a client-side
        # workflow result type is not supplied.  The rest of this method uses
        # the workflow DTO (including candidate status/output attributes), so
        # an untyped result raises after the stream has emitted its start
        # events and leaves the UI's candidate cards looking permanently live.
        result_task = asyncio.create_task(reviewer_handle.result())
        text_seen: dict[str, str] = {key: "" for key in sources}

        def event_message_id(key: str) -> str:
            return (
                reviewer_id
                if key == "reviewer"
                else (f"ensemble-candidate:{run_id}:{key.removeprefix('candidate:')}")
            )

        try:
            for name in candidates:
                key = f"candidate:{name}"
                message_id = f"ensemble-candidate:{run_id}:{name}"
                yield CustomEvent(
                    name="ensemble.candidate.started",
                    value={"source": key, "approach": name},
                )
                yield TextMessageStartEvent(message_id=message_id, role="assistant", source=key)
            reviewer_id = f"ensemble-assistant:{run_id}"
            yield TextMessageStartEvent(message_id=reviewer_id, role="assistant", source="reviewer")
            while not result_task.done():
                if queue.empty() and all(task.done() for task in subscribers):
                    await asyncio.wait({result_task}, return_when=asyncio.ALL_COMPLETED)
                    break
                if queue.empty():
                    queue_task = asyncio.create_task(queue.get())
                    done, _ = await asyncio.wait(
                        {queue_task, result_task}, return_when=asyncio.FIRST_COMPLETED
                    )
                    if result_task in done:
                        queue_task.cancel()
                        break
                    key, item = queue_task.result()
                else:
                    key, item = queue.get_nowait()
                delta = self.raw_text_delta(getattr(item, "data", item))
                if delta is None:
                    continue
                offsets[key] = max(offsets[key], int(getattr(item, "offset", offsets[key])) + 1)
                message_id = event_message_id(key)
                text_seen[key] += delta
                yield TextMessageContentEvent(
                    message_id=message_id,
                    delta=delta,
                    source=key,
                    cursor=self.encode_cursor(offsets),
                )
            try:
                output = await result_task
            except Exception:
                yield RunErrorEvent(
                    message="The assistant could not complete this run", code="run_error"
                )
                return
            # Subscribers can have queued items at the exact completion boundary.
            while not queue.empty():
                key, item = queue.get_nowait()
                delta = self.raw_text_delta(getattr(item, "data", item))
                if delta:
                    offsets[key] = max(offsets[key], int(getattr(item, "offset", offsets[key])) + 1)
                    text_seen[key] += delta
                    message_id = event_message_id(key)
                    yield TextMessageContentEvent(
                        message_id=message_id,
                        delta=delta,
                        source=key,
                        cursor=self.encode_cursor(offsets),
                    )
            final: dict[str, str] = {"reviewer": str(output.reviewer_output or "")}
            final.update(
                {
                    f"candidate:{item.approach}": (
                        item.final_output
                        if item.status == "completed"
                        else "Candidate unavailable."
                    )
                    for item in output.candidates
                }
            )
            for key, value in final.items():
                if key not in sources:
                    continue
                remainder = (
                    value[len(text_seen[key]) :] if value.startswith(text_seen[key]) else value
                )
                if remainder:
                    yield TextMessageContentEvent(
                        message_id=event_message_id(key), delta=remainder, source=key
                    )
                text_seen[key] = value
            for key in sources:
                yield TextMessageEndEvent(message_id=event_message_id(key), source=key)
                if key != "reviewer":
                    name = key.removeprefix("candidate:")
                    status = next(
                        (x.status for x in output.candidates if x.approach == name), "failed"
                    )
                    yield CustomEvent(
                        name=f"ensemble.candidate.{status}",
                        value={"source": key, "approach": name},
                    )
            yield RunFinishedEvent(thread_id=thread_id, run_id=run_id)
        finally:
            for task in subscribers:
                task.cancel()
            await asyncio.gather(*subscribers, return_exceptions=True)
            if not result_task.done():
                result_task.cancel()
                await asyncio.gather(result_task, return_exceptions=True)

    async def handle(self, workflow_id: str):
        return await self.backend.handle(workflow_id)

    async def preflight(self) -> None:
        """Verify durable execution is available before opening an SSE response."""
        await self.backend.preflight()

    async def get_run(self, chat_id: int, run_id: str):
        return await self.repository.get_run(chat_id, run_id)

    async def cancel(self, chat_id: int, run_id: str, workflow_id: str) -> None:
        await (await self.handle(workflow_id)).cancel(reason="cancelled by client")
        await self.repository.mark_run_cancelled(chat_id, run_id)
