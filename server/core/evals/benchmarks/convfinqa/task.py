import sys
from pathlib import Path
from typing import Any

# Inspect loads task files in an isolated module context during `inspect eval`.
# Its synthetic package name is non-empty, so add the server project root when
# loading this file directly rather than importing it as part of ``evals``.
core_root = Path(__file__).resolve().parents[3]
if str(core_root) not in sys.path:
    sys.path.insert(0, str(core_root))

# Evals are intentionally source tasks outside the production wheel. Keeping the
# dataset beside this task makes ``inspect eval <path>`` independent of cwd,
# without adding an Inspect entry point (or packaging benchmark-only code).
DEFAULT_DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "convfinqa_dataset.json"

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import MemoryDataset, Sample  # noqa: E402
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser  # noqa: E402
from inspect_ai.solver import TaskState, solver  # noqa: E402

from evals.benchmarks.convfinqa.cases_schema import ConversationCase  # noqa: E402
from evals.benchmarks.convfinqa.scorers import (  # noqa: E402
    contains_accuracy,
    conversation_exact_accuracy,
    numeric_accuracy,
    parse_failure_rate,
    turn_execution_accuracy,
)
from evals.config_schema import EvaluationConfig  # noqa: E402
from evals.convfinqa import load_cases  # noqa: E402
from evals.direct import execute_direct  # noqa: E402
from evals.inspect_support import record_application_usage  # noqa: E402
from evals.targets import component_metadata, resolve_target  # noqa: E402


def _csv(value: str | int | list[str] | list[int]) -> tuple[str, ...]:
    values = value if isinstance(value, list) else str(value).split(",")
    return tuple(str(item).strip() for item in values if str(item).strip())


def build_task(
    cases: tuple[ConversationCase, ...],
    config: EvaluationConfig,
) -> Task:
    targets = tuple(resolve_target(target_id) for target_id in config.targets)
    # Apply this before the record/target cartesian product so every approach
    # receives exactly the same records.
    selected_cases = cases[: config.record_limit] if config.record_limit is not None else cases
    samples = [
        Sample(
            id=f"{case.dataset_id}:{target.id}",
            input=case.turns[0].question,
            target=case.turns[0].answer or "",
            metadata={
                "case": case.model_dump(mode="json"),
                "target": target.id,
                "approach": target.id,
                "dataset_id": case.dataset_id,
                "source_id": case.source_id,
                "target_metadata": target.metadata(config.application_model),
                "prompt_components": component_metadata(target.id),
            },
        )
        for case in selected_cases
        for target in targets
    ]

    @solver
    def run_application():
        async def solve(state: TaskState, generate: Any) -> TaskState:
            case = ConversationCase.model_validate(state.metadata["case"])
            target = resolve_target(str(state.metadata["target"]))
            observations = await execute_direct(case, target, config)
            record_application_usage(observations)
            state.messages.clear()
            for observation in observations:
                state.messages.append(ChatMessageUser(content=observation.question))
                state.messages.append(
                    ChatMessageAssistant(content=observation.actual, source="generate")
                )
            state.metadata["observations"] = [
                observation.model_dump(mode="json") for observation in observations
            ]
            return state

        return solve

    return Task(
        name="convfinqa",
        dataset=MemoryDataset(samples=samples, name="convfinqa"),
        solver=run_application(),
        scorer=[
            turn_execution_accuracy(),
            conversation_exact_accuracy(),
            parse_failure_rate(),
            numeric_accuracy(),
            contains_accuracy(),
        ],
        model=None,
        metadata={
            "application_model": config.application_model,
        },
    )


@task
def convfinqa(
    dataset_ids: str | int | list[str | int] | None = None,
    targets: str | list[str] = "baseline:v1,baseline-tool:v1,program-of-thought:v1",
    application_model: str = "gpt-5.6-luna",
    dataset_path: str | None = None,
    split: str = "dev",
    record_limit: int | None = None,
) -> Task:
    """Run fixed ConvFinQA conversations through the production application."""
    config = EvaluationConfig(
        dataset_ids=_csv(dataset_ids or ""),
        targets=_csv(targets),
        application_model=application_model,
        dataset_path=dataset_path or str(DEFAULT_DATASET_PATH),
        split=split or "dev",
        record_limit=record_limit,
    )
    cases = load_cases(config)
    return build_task(cases, config)
