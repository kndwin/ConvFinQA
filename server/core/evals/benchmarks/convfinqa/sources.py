from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import cast

from evals.benchmarks.convfinqa.cases import case_from_payload
from evals.benchmarks.convfinqa.cases_schema import ConversationCase
from evals.config_schema import EvaluationConfig


async def load_cases_async(config: EvaluationConfig) -> tuple[ConversationCase, ...]:
    if config.dataset_path is not None:
        return _load_local_cases(config)
    dataset_ids = config.dataset_ids or ("3139",)
    if any(not item.isdigit() or int(item) <= 0 for item in dataset_ids):
        raise ValueError("database dataset IDs must be positive integers")
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
        repository = DatasetConversationRepository(session, cast(Observability, NOOP_OBSERVABILITY))
        for dataset_id in dataset_ids:
            item = await repository.get(
                DatasetConversationRepositoryGetParams(dataset_conversation_id=int(dataset_id))
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


def _load_local_cases(config: EvaluationConfig) -> tuple[ConversationCase, ...]:
    path = config.dataset_path
    assert path is not None
    try:
        with open(path, encoding="utf-8") as stream:
            payload = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError(f"local ConvFinQA dataset is invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("local ConvFinQA dataset must be a top-level split mapping")
    split = config.split or "dev"
    records = payload.get(split)
    if not isinstance(records, list):
        raise ValueError(f"local ConvFinQA split {split!r} must be a list")
    requested = set(config.dataset_ids)
    seen: set[str] = set()
    selected: list[dict[str, object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"local ConvFinQA {split!r} record {index} must be an object")
        if "id" not in record or record["id"] is None or not str(record["id"]).strip():
            raise ValueError(f"local ConvFinQA {split!r} record {index} has no valid id")
        source_id = str(record["id"])
        if source_id in seen:
            raise ValueError(f"duplicate ConvFinQA source id {source_id!r} in split {split!r}")
        seen.add(source_id)
        if not requested or source_id in requested:
            selected.append(record)
    if requested:
        missing = requested - seen
        if missing:
            raise ValueError(
                f"requested ConvFinQA dataset IDs not found in {split!r}: {sorted(missing)}"
            )
    return tuple(case_from_payload(record) for record in selected)


def load_cases(config: EvaluationConfig) -> tuple[ConversationCase, ...]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(load_cases_async(config))

    # Inspect constructs task factories inside its event loop. Source loading is
    # required to build the Dataset, so isolate the async DB loader in a
    # short-lived thread rather than nesting asyncio.run().
    def run_loader() -> tuple[ConversationCase, ...]:
        return asyncio.run(load_cases_async(config))

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run_loader).result()
