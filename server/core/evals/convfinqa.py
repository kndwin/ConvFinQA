import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

import httpx

from evals.models_schema import ConversationCase, EvaluationConfig, ExpectedTurn


def case_from_payload(payload: dict[str, Any]) -> ConversationCase:
    raw = payload.get("dialogue_json")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError("dialogue_json must be a JSON object")
    questions = raw.get("conv_questions")
    answers = raw.get("conv_answers")
    if not isinstance(questions, list) or not questions:
        raise ValueError("conv_questions must be a non-empty list")
    if not isinstance(answers, list):
        raise ValueError("conv_answers must be a list")
    turns = []
    for index, question in enumerate(questions):
        if not isinstance(question, str) or not question.strip():
            raise ValueError("each ConvFinQA question must be a non-empty string")
        answer = answers[index] if index < len(answers) else None
        turns.append(
            ExpectedTurn(
                question=question.strip(),
                answer=None if answer is None else str(answer),
            )
        )
    return ConversationCase(
        dataset_id=int(payload["id"]),
        document=str(payload.get("doc_json") or ""),
        turns=tuple(turns),
        source_id=None if payload.get("source_id") is None else str(payload["source_id"]),
    )


async def load_cases_async(config: EvaluationConfig) -> tuple[ConversationCase, ...]:
    if config.executor == "remote":
        async with httpx.AsyncClient(base_url=str(config.base_url).rstrip("/")) as client:
            payloads = []
            for dataset_id in config.dataset_ids:
                response = await client.get(f"/dataset-conversations/{dataset_id}")
                response.raise_for_status()
                payloads.append(response.json())
    else:
        from src.module.dataset_conversations.dataset_conversations_repository import (
            DatasetConversationRepository,
        )
        from src.module.dataset_conversations.dataset_conversations_repository_schema import (
            DatasetConversationRepositoryGetParams,
        )
        from src.platform.database.database import session_factory
        from src.platform.observability import NOOP_OBSERVABILITY, Observability

        payloads = []
        async with session_factory() as session:
            repository = DatasetConversationRepository(
                session, cast(Observability, NOOP_OBSERVABILITY)
            )
            for dataset_id in config.dataset_ids:
                item = await repository.get(
                    DatasetConversationRepositoryGetParams(dataset_conversation_id=dataset_id)
                )
                if item is None:
                    raise ValueError(f"Dataset conversation not found: {dataset_id}")
                payloads.append(
                    {
                        "id": item.id,
                        "doc_json": item.doc_json or "",
                        "dialogue_json": item.dialogue_json,
                        "source_id": getattr(item, "source_id", None),
                    }
                )
    return tuple(case_from_payload(payload) for payload in payloads)


def load_cases(config: EvaluationConfig) -> tuple[ConversationCase, ...]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(load_cases_async(config))

    # Inspect constructs task factories inside its event loop. Source loading is
    # required to build the Dataset, so isolate the async DB/HTTP loader in a
    # short-lived thread rather than nesting asyncio.run().
    def run_loader() -> tuple[ConversationCase, ...]:
        return asyncio.run(load_cases_async(config))

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run_loader).result()
