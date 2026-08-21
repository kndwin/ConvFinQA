"""Inspect scorer factories for ConvFinQA."""

import re
from typing import Any

from inspect_ai.scorer import Score, grouped, mean, scorer, stderr
from inspect_ai.solver import TaskState

from evals.benchmarks.convfinqa.structured import canonicalize_gold_execution
from evals.direct_schema import ObservedTurn
from evals.scoring import (
    EXECUTION_RELATIVE_TOLERANCE,
    RELATIVE_TOLERANCE,
    contains_text,
    score_dict,
    score_numeric,
    score_numeric_execution,
)
from evals.scoring.numeric_schema import NumericScore

_COMPARISON_METRICS = [
    mean(),
    stderr(),
    grouped(mean(), "approach", all=False, name_template="{group_name}_mean"),
    grouped(stderr(), "approach", all=False, name_template="{group_name}_stderr"),
]


@scorer(metrics=_COMPARISON_METRICS)
def numeric_accuracy():
    """Legacy 1%-tolerance numeric diagnostic."""

    async def score(state: TaskState, target: Any) -> Score:
        del target
        observations = tuple(
            ObservedTurn.model_validate(item) for item in state.metadata.get("observations", [])
        )
        structured = str(state.metadata.get("target", "")).endswith((":v3", ":v1")) and str(
            state.metadata.get("target", "")
        ).startswith(("baseline:v3", "evidence:v1", "program-of-thought:v3"))
        if structured:
            details = tuple(_strict_structured(observation) for observation in observations)
        else:
            details = tuple(
                score_numeric(
                    observation.executed_answer or observation.expected or "",
                    observation.actual,
                    question=observation.question,
                )
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
                "relative_tolerance": RELATIVE_TOLERANCE,
                "limitations": (
                    "Fallback extraction uses the final suitable result; an explicit "
                    "Final answer candidate always has exclusive priority."
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


def _normalized(text: str | None) -> str:
    value = " ".join((text or "").strip().lower().split())
    explicit = re.search(r"(?:final answer|answer)(?:\s+is)?\s*[:=]?\s*(.+)$", value, re.I)
    if explicit:
        value = explicit.group(1)
        # Final responses sometimes add a short explanation.  The answer marker
        # makes the first sentence an unambiguous, deterministic extraction.
        value = re.split(r"[.!?](?:\s|$)", value, maxsplit=1)[0]
    value = value.strip(" \t\r\n.:;!?\"'")
    # Make the common answer prefix transparent for boolean and text answers.
    value = re.sub(r"^(?:final answer|answer)(?:\s+is)?\s*[:=]?\s*", "", value)
    return value.strip(" \t\r\n.:;!?\"'")


def _text_answer(expected: str | None, actual: str) -> tuple[bool, bool, str]:
    expected_value = _normalized(expected)
    actual_value = _normalized(actual)
    if not expected_value or not actual_value:
        return False, bool(actual_value), actual_value
    if expected_value in {"yes", "no", "true", "false"}:
        aliases = {"yes": "true", "true": "true", "no": "false", "false": "false"}
        return aliases.get(expected_value) == aliases.get(actual_value), True, actual_value
    return expected_value == actual_value, True, actual_value


def _execution_detail(observation: ObservedTurn) -> tuple[bool, bool, dict[str, object]]:
    """Return (correct, usable, serializable details), without consulting model judges."""
    expected = observation.executed_answer or observation.expected
    if observation.actual.lstrip().startswith("{"):
        structured = _strict_structured(observation)
        usable = structured.extraction_method != "invalid-json"
        return structured.exact_match, usable, score_dict(structured)
    # Numeric parsing is deliberately selected from the reference answer's type,
    # never by searching for whichever candidate happens to be closest to gold.
    if (
        expected
        and score_numeric_execution(expected, expected, observation.question).expected is not None
    ):
        result = score_numeric_execution(expected, observation.actual, observation.question)
        detail = score_dict(result)
        return result.exact_match, result.actual is not None, detail
    correct, usable, extracted = _text_answer(expected, observation.actual)
    return (
        correct,
        usable,
        {
            "exact_match": correct,
            "extraction_method": "normalized-text" if usable else "no-answer",
            "expected": _normalized(expected),
            "actual": extracted,
        },
    )


@scorer(metrics=_COMPARISON_METRICS)
def turn_execution_accuracy():
    """Answer-type-aware deterministic execution accuracy (macro per conversation)."""

    async def score(state: TaskState, target: Any) -> Score:
        del target
        observations = tuple(
            ObservedTurn.model_validate(item) for item in state.metadata.get("observations", [])
        )
        results = tuple(_execution_detail(item) for item in observations)
        correct = sum(item[0] for item in results)
        value = correct / len(results) if results else 0.0
        return Score(
            value=value,
            answer=observations[-1].actual if observations else "",
            explanation=f"{correct}/{len(results)} turns correct (per-conversation mean)",
            metadata={
                "correct_turns": correct,
                "total_turns": len(results),
                "fully_correct_conversation": bool(results) and all(item[0] for item in results),
                "relative_tolerance": EXECUTION_RELATIVE_TOLERANCE,
                "turns": [
                    {
                        "turn": observation.turn,
                        "correct": item[0],
                        "usable_answer": item[1],
                        "score": item[2],
                    }
                    for observation, item in zip(observations, results, strict=True)
                ],
            },
        )

    return score


@scorer(metrics=_COMPARISON_METRICS)
def conversation_exact_accuracy():
    """1 only when every turn in a conversation is correct."""

    async def score(state: TaskState, target: Any) -> Score:
        del target
        observations = tuple(
            ObservedTurn.model_validate(item) for item in state.metadata.get("observations", [])
        )
        results = tuple(_execution_detail(item)[0] for item in observations)
        exact = bool(results) and all(results)
        return Score(
            value=1.0 if exact else 0.0,
            answer="",
            explanation="all turns correct" if exact else "at least one turn incorrect",
            metadata={"fully_correct_conversation": exact},
        )

    return score


@scorer(metrics=_COMPARISON_METRICS)
def parse_failure_rate():
    """Fraction of turns for which no usable final answer could be extracted."""

    async def score(state: TaskState, target: Any) -> Score:
        del target
        observations = tuple(
            ObservedTurn.model_validate(item) for item in state.metadata.get("observations", [])
        )
        failures = sum(not _execution_detail(item)[1] for item in observations)
        return Score(
            value=failures / len(observations) if observations else 0.0,
            answer="",
            explanation=f"{failures}/{len(observations)} turns had no usable answer",
            metadata={"parse_failures": failures, "total_turns": len(observations)},
        )

    return score


def _strict_structured(observation: ObservedTurn):
    """Strict target scorer: malformed output is simply an incorrect turn."""
    try:
        artifact = observation.structured or {}
        if not artifact.get("valid") or "canonical" not in artifact:
            raise ValueError("invalid structured artifact")
        actual = artifact["canonical"]
        expected_raw = str(observation.executed_answer or observation.expected or "")
        try:
            expected = canonicalize_gold_execution(expected_raw).model_dump(mode="json")
        except ValueError:
            actual_kind = actual.get("kind")
            if actual_kind == "boolean":
                normalized = {"yes": "true", "no": "false", "true": "true", "false": "false"}.get(
                    expected_raw.strip().lower()
                )
                if normalized is None:
                    raise ValueError("non-boolean expected answer") from None
                expected = {"kind": "boolean", "value": normalized}
            elif actual_kind == "text":
                expected = {"kind": "text", "value": expected_raw}
            else:
                raise ValueError("numeric gold required") from None
        equal = actual.get("kind") == expected["kind"] and actual.get("value") == expected["value"]
        return NumericScore(
            exact_match=equal,
            absolute_error=None,
            relative_error=None,
            expected=None,
            actual=None,
            extraction_method="strict-json",
            extracted_text=artifact.get("raw_action_stage"),
        )
    except Exception:
        return NumericScore(
            exact_match=False,
            absolute_error=None,
            relative_error=None,
            expected=None,
            actual=None,
            extraction_method="invalid-json",
            extracted_text=None,
        )


@scorer(metrics=_COMPARISON_METRICS)
def contains_accuracy():
    """Legacy literal substring diagnostic; not an execution correctness score."""

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
