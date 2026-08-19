import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal, cast

# Inspect loads task files in an isolated module context during `inspect eval`.
# Its synthetic package name is non-empty, so add the server root unconditionally.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser, ModelUsage
from inspect_ai.scorer import Score, mean, scorer
from inspect_ai.solver import TaskState, solver

from evals.convfinqa import load_cases
from evals.execution import execute_direct, execute_remote
from evals.models_schema import ConversationCase, EvaluationConfig, ObservedTurn, TargetSpec
from evals.scoring import contains_text, score_dict, score_numeric
from evals.targets import resolve_target

Executor = Callable[
    [ConversationCase, TargetSpec, EvaluationConfig], Awaitable[tuple[ObservedTurn, ...]]
]


def record_application_usage(observations: tuple[ObservedTurn, ...]) -> None:
    """Bridge real application usage into Inspect's sample bookkeeping.

    Inspect 0.3.259 has no public API for an externally executed completion. Its
    native bookkeeping primitive is nevertheless provider-independent: updating
    the active sample's model-usage map does not create a model or make a call.
    """
    # inspect-ai 0.3.259 has no public API for recording externally executed usage.
    # Keep this narrow pin: these private bookkeeping helpers are version-sensitive.
    from inspect_ai.model._model import sample_model_usage, set_model_usage

    usage_by_model: dict[str, ModelUsage] = {}
    for turn in observations:
        for usage in turn.model_usage:
            current = usage_by_model.get(usage.model, ModelUsage())
            usage_by_model[usage.model] = current + ModelUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                input_tokens_cache_read=usage.cached_input_tokens,
                input_tokens_cache_write=usage.cache_write_tokens,
                reasoning_tokens=usage.reasoning_tokens,
            )
    for model, usage in usage_by_model.items():
        set_model_usage(model, usage, sample_model_usage())


def _csv(value: str | int | list[str] | list[int]) -> tuple[str, ...]:
    values = value if isinstance(value, list) else str(value).split(",")
    return tuple(str(item).strip() for item in values if str(item).strip())


@scorer(metrics=[mean()])
def numeric_accuracy():
    """Score every conversation turn using candidate-based numeric matching."""

    async def score(state: TaskState, target: Any) -> Score:
        del target
        observations = tuple(
            ObservedTurn.model_validate(item) for item in state.metadata.get("observations", [])
        )
        details = tuple(
            score_numeric(observation.expected or "", observation.actual)
            for observation in observations
        )
        accuracy = sum(detail.exact_match for detail in details) / len(details) if details else 0.0
        return Score(
            value=accuracy,
            answer=observations[-1].actual if observations else "",
            explanation=(
                f"{sum(detail.exact_match for detail in details)}/{len(details)} turns correct"
            ),
            metadata={
                "fully_correct_conversation": bool(details)
                and all(detail.exact_match for detail in details),
                "relative_tolerance": 0.01,
                "limitations": (
                    "Candidate-based numeric matching can pass intermediate mentions; "
                    "an explicit Final answer/Answer is candidate takes priority."
                ),
                "turns": [
                    {
                        "observation": observation.model_dump(mode="json"),
                        "score": score_dict(detail),
                    }
                    for observation, detail in zip(observations, details, strict=True)
                ],
            },
        )

    return score


@scorer(metrics=[mean()])
def contains_accuracy():
    """Score every conversation turn using literal substring matching."""

    async def score(state: TaskState, target: Any) -> Score:
        del target
        observations = tuple(
            ObservedTurn.model_validate(item) for item in state.metadata.get("observations", [])
        )
        details = tuple(
            contains_text(observation.expected, observation.actual) for observation in observations
        )
        matching = sum(details)
        accuracy = matching / len(details) if details else 0.0
        return Score(
            value=accuracy,
            answer=observations[-1].actual if observations else "",
            explanation=f"{matching}/{len(details)} turns contain the expected text",
            metadata={
                "fully_correct_conversation": bool(details) and all(details),
                "turns": [
                    {
                        "turn": observation.turn,
                        "expected": observation.expected,
                        "actual": observation.actual,
                        "contains": contains,
                    }
                    for observation, contains in zip(observations, details, strict=True)
                ],
                "limitations": (
                    "Literal, case-sensitive substring matching can pass intermediate "
                    "mentions and is sensitive to formatting."
                ),
            },
        )

    return score


def build_task(
    cases: tuple[ConversationCase, ...],
    config: EvaluationConfig,
    executor: Executor,
) -> Task:
    targets = tuple(resolve_target(target_id) for target_id in config.targets)
    samples = [
        Sample(
            id=f"{case.dataset_id}:{target.id}",
            input=case.turns[0].question,
            target=case.turns[0].answer or "",
            metadata={
                "case": case.model_dump(mode="json"),
                "target": target.id,
                "target_metadata": target.metadata(config.application_model),
            },
        )
        for case in cases
        for target in targets
    ]

    @solver
    def run_application():
        async def solve(state: TaskState, generate: Any) -> TaskState:
            case = ConversationCase.model_validate(state.metadata["case"])
            target = resolve_target(str(state.metadata["target"]))
            observations = await executor(case, target, config)
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
        scorer=[numeric_accuracy(), contains_accuracy()],
        model=None,
        metadata={
            "executor": config.executor,
            "application_model": config.application_model,
        },
    )


@task
def convfinqa(
    dataset_ids: str | int | list[int] = "3139",
    targets: str | list[str] = "baseline:v1,baseline-tool:v1,program-of-thought:v1",
    executor: str = "direct",
    application_model: str = "gpt-5.6-luna",
    base_url: str = "http://127.0.0.1:8000",
    keep_sessions: bool = False,
) -> Task:
    """Run fixed ConvFinQA conversations through the production application."""
    config = EvaluationConfig(
        dataset_ids=tuple(int(item) for item in _csv(dataset_ids)),
        targets=_csv(targets),
        executor=cast(Literal["direct", "remote"], executor),
        application_model=application_model,
        base_url=base_url,
        keep_sessions=keep_sessions,
    )
    cases = load_cases(config)
    selected_executor = execute_direct if config.executor == "direct" else execute_remote
    return build_task(cases, config, selected_executor)
