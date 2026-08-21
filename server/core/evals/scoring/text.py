"""Text scoring and score serialization helpers."""

from evals.scoring.numeric_schema import NumericScore


def contains_text(expected_text: str | None, actual_text: str) -> bool:
    return bool(expected_text) and expected_text in actual_text


def score_dict(score: NumericScore) -> dict[str, object]:
    return score.model_dump(mode="json")


__all__ = ["contains_text", "score_dict"]
