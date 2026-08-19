import re
from decimal import Decimal, InvalidOperation

from evals.numeric_schema import NumericScore

_NUMBER = re.compile(r"(?<![\w.])[−+\-]?\$?\d[\d,]*(?:\.\d+)?%?")


def _number(text: str) -> tuple[Decimal, str] | None:
    cleaned = text.strip().replace(",", "").replace("$", "").replace("−", "-")
    percent = cleaned.endswith("%")
    if percent:
        cleaned = cleaned[:-1]
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return (value / 100 if percent else value), ("percent" if percent else "number")


def _candidates(text: str) -> list[tuple[str, Decimal, str]]:
    result = []
    for match in _NUMBER.finditer(text or ""):
        parsed = _number(match.group(0))
        if parsed is not None:
            value, kind = parsed
            result.append((match.group(0), value, kind))
    return result


def _explicit_candidate(text: str) -> tuple[str, Decimal, str] | None:
    explicit = re.search(
        rf"(?:final answer(?:\s+is)?|answer is)\s*[:=]?\s*({_NUMBER.pattern})",
        text or "",
        re.I,
    )
    if explicit is None:
        return None
    token = explicit.group(1)
    parsed = _number(token)
    return (token, parsed[0], parsed[1]) if parsed is not None else None


def extract_numeric(text: str) -> tuple[float | None, str, str | None]:
    """Compatibility helper returning the first/intended numeric token.

    Scoring itself uses all candidates; this helper preserves the small public
    API used by the eval harness and tests.
    """
    candidates = list(_NUMBER.finditer(text or ""))
    if not candidates:
        return None, "no-number", None
    explicit = re.search(
        rf"(?:final answer(?:\s+is)?|answer is)\s*[:=]?\s*({_NUMBER.pattern})", text, re.I
    )
    selected = explicit or candidates[0]
    parsed = _number(selected.group(1) if explicit else selected.group(0))
    if parsed is None:
        return None, "no-number", selected.group(0)
    value, kind = parsed
    return (
        float(value),
        (f"explicit-{kind}" if explicit else f"fallback-first-number-{kind}"),
        selected.group(0),
    )


def score_numeric(expected_text: str, actual_text: str) -> NumericScore:
    expected_candidates = _candidates(expected_text)
    expected_explicit = _explicit_candidate(expected_text)
    expected_item = expected_explicit or (expected_candidates[0] if expected_candidates else None)
    expected = float(expected_item[1]) if expected_item else None
    actual_candidates = _candidates(actual_text)
    actual_explicit = _explicit_candidate(actual_text)
    eligible = [actual_explicit] if actual_explicit else actual_candidates
    if expected_item is None:
        return NumericScore(
            exact_match=False,
            absolute_error=None,
            relative_error=None,
            expected=None,
            actual=None,
            extraction_method="no-number",
            extracted_text=None,
        )
    expected_value, expected_kind = expected_item[1], expected_item[2]
    compatible = [
        item
        for item in eligible
        if item is not None
        and (item[2] == "percent" if expected_kind == "percent" else item[2] != "percent")
    ]
    details = [
        {
            "token": token,
            "value": float(value),
            "kind": kind,
            "compatible": kind == expected_kind
            if expected_kind == "percent"
            else kind != "percent",
        }
        for token, value, kind in eligible
        if token is not None
    ]
    if not compatible:
        return NumericScore(
            exact_match=False,
            absolute_error=None,
            relative_error=None,
            expected=expected,
            actual=None,
            extraction_method=(
                "explicit-incompatible" if actual_explicit else "no-compatible-number"
            ),
            extracted_text=actual_explicit[0] if actual_explicit else None,
            selected_token=actual_explicit[0] if actual_explicit else None,
            candidate_details=details,
        )
    selected = min(compatible, key=lambda item: abs(item[1] - expected_value))
    actual_token, actual_decimal, _ = selected
    actual = float(actual_decimal)
    absolute_decimal = abs(actual_decimal - expected_value)
    relative_decimal = absolute_decimal / abs(expected_value) if expected_value else None
    tolerance = abs(expected_value) * Decimal("0.01")
    matches = absolute_decimal <= (tolerance if expected_value else Decimal("1e-12"))
    return NumericScore(
        exact_match=matches,
        absolute_error=float(absolute_decimal),
        relative_error=(
            float(relative_decimal) if relative_decimal is not None else (0.0 if matches else None)
        ),
        expected=expected,
        actual=actual,
        extraction_method="explicit" if actual_explicit else "candidate-search",
        extracted_text=actual_token,
        selected_token=actual_token,
        candidate_details=details,
    )


def contains_text(expected_text: str | None, actual_text: str) -> bool:
    """Return whether a non-empty expected answer occurs literally in actual text.

    This intentionally has Evalite ``contains`` semantics: comparison is case
    sensitive and does not normalize formatting or select an answer candidate.
    Empty or missing expected answers are failures rather than matching every
    string.
    """
    return bool(expected_text) and expected_text in actual_text


def score_dict(score: NumericScore) -> dict[str, object]:
    return score.model_dump(mode="json")
