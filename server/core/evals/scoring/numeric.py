"""Numeric ConvFinQA scoring.

Values are compared in execution space: percentages are fractions and explicit
million/billion suffixes are converted only when the question requests a unit.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from evals.scoring.numeric_schema import NumericScore

_NUMBER = re.compile(r"(?<![\w.])[−+\-]?\$?\d[\d,]*(?:\.\d+)?%?")
RELATIVE_TOLERANCE = 0.01
"""Tolerance retained for the original, diagnostic numeric scorer."""
EXECUTION_RELATIVE_TOLERANCE = 0.0001
_FIVE = Decimal("0.00001")


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
            suffix = re.match(r"\s*(millions?|billions?)\b", (text or "")[match.end() :], re.I)
            token = match.group(0) + (f" {suffix.group(1)}" if suffix else "")
            result.append((token, *parsed))
    # Defensible sign inference for natural-language answers, but never for an
    # explicit Final answer (handled separately and therefore positive-safe).
    if (
        re.search(
            r"(?:decreased|decline|decrease|down|loss)\s+(?:by|of)?\s*"
            r"[−+\-]?\$?\d[\d,]*(?:\.\d+)?%?\s*"
            r"(?:millions?|billions?)?\s*[.!]?\s*$",
            text or "",
            re.I,
        )
        and result
        and result[-1][1] > 0
    ):
        token, value, kind = result[-1]
        result[-1] = (token, -value, kind)
    return result


def _explicit_candidate(text: str) -> tuple[str, Decimal, str] | None:
    match = re.search(
        r"(?:final answer(?:\s+is)?|answer is)\s*[:=]?\s*(" + _NUMBER.pattern + r")",
        text or "",
        re.I,
    )
    if match is None:
        return None
    token = match.group(1)
    parsed = _number(token)
    if parsed:
        suffix = re.match(r"\s*(millions?|billions?)\b", (text or "")[match.end() :], re.I)
        if suffix:
            token += " " + suffix.group(1)
    return (token, parsed[0], parsed[1]) if parsed else None


def extract_numeric(text: str) -> tuple[float | None, str, str | None]:
    explicit = _explicit_candidate(text)
    candidates = _candidates(text)
    selected = explicit or (candidates[-1] if candidates else None)
    if selected is None:
        return None, "no-number", None
    token, value, kind = selected
    return float(value), f"{'explicit' if explicit else 'fallback-last'}-{kind}", token


def _unit_adjust(value: Decimal, token: str, question: str) -> Decimal:
    token_unit = re.search(r"\b(million|millions|billion|billions)\b", token, re.I)
    requested = re.search(r"\bin\s+(?:the\s+)?(millions?|billions?)\b", question or "", re.I)
    if not token_unit or not requested:
        return value
    source = token_unit.group(1).lower().startswith("billion")
    target = requested.group(1).lower().startswith("billion")
    if source and not target:
        return value * 1000
    if not source and target:
        return value / 1000
    return value


def _score_numeric(
    expected_text: str, actual_text: str, question: str = "", *, relative_tolerance: Decimal
) -> NumericScore:
    expected_candidates = _candidates(expected_text)
    expected_item = _explicit_candidate(expected_text) or (
        expected_candidates[-1] if expected_candidates else None
    )
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
    expected_value = _unit_adjust(expected_item[1], expected_item[0], question)
    # The legacy scorer historically rounded to five places.  Strict execution
    # scoring keeps Decimal precision so the advertised boundary is exact.
    if relative_tolerance >= Decimal("0.001"):
        expected_value = expected_value.quantize(_FIVE, rounding=ROUND_HALF_UP)
    explicit = _explicit_candidate(actual_text)
    raw = _candidates(actual_text)
    candidates = [_unit_adjust(v, token, question) for token, v, _ in raw]
    if explicit:
        selected_value = _unit_adjust(explicit[1], explicit[0], question)
        selected_token = explicit[0]
        method = "explicit-final"
    elif raw:
        # Last answer clause / final expression wins; do not inspect distance to gold.
        selected_index = len(raw) - 1
        # A trailing reporting year in prose is context, not the result.
        while (
            selected_index > 0
            and candidates[selected_index] == candidates[selected_index].to_integral_value()
            and 1900 <= candidates[selected_index] <= 2100
        ):
            selected_index -= 1
        selected_value = candidates[selected_index]
        selected_token = raw[selected_index][0]
        method = "fallback-last-candidate"
    else:
        selected_value = None
        selected_token = None
        method = "no-number"
    details = [{"token": t, "value": float(v), "kind": k} for t, v, k in raw]
    if selected_value is None:
        return NumericScore(
            exact_match=False,
            absolute_error=None,
            relative_error=None,
            expected=float(expected_value),
            actual=None,
            extraction_method=method,
            extracted_text=None,
            candidate_details=details,
            relative_tolerance=float(relative_tolerance),
        )
    actual_value = selected_value
    if relative_tolerance >= Decimal("0.001"):
        actual_value = actual_value.quantize(_FIVE, rounding=ROUND_HALF_UP)
    error = abs(actual_value - expected_value)
    tolerance = max(_FIVE, abs(expected_value) * relative_tolerance)
    match = error <= tolerance
    relative = error / abs(expected_value) if expected_value else None
    return NumericScore(
        exact_match=match,
        absolute_error=float(error),
        relative_error=float(relative) if relative is not None else 0.0,
        expected=float(expected_value),
        actual=float(actual_value),
        extraction_method=method,
        extracted_text=selected_token,
        selected_token=selected_token,
        candidate_details=details,
        relative_tolerance=float(relative_tolerance),
    )


def score_numeric(expected_text: str, actual_text: str, question: str = "") -> NumericScore:
    """Legacy numeric comparison (1% tolerance), kept for result comparability."""
    return _score_numeric(
        expected_text, actual_text, question, relative_tolerance=Decimal(str(RELATIVE_TOLERANCE))
    )


def score_numeric_execution(
    expected_text: str, actual_text: str, question: str = ""
) -> NumericScore:
    """Strict execution comparison used by the primary ConvFinQA scorer."""
    return _score_numeric(
        expected_text,
        actual_text,
        question,
        relative_tolerance=Decimal(str(EXECUTION_RELATIVE_TOLERANCE)),
    )
