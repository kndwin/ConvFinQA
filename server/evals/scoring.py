import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class NumericScore:
    exact_match: bool
    absolute_error: float | None
    relative_error: float | None
    expected: float | None
    actual: float | None
    extraction_method: str
    extracted_text: str | None


_NUMBER = re.compile(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")


def _number(text: str) -> tuple[Decimal, str] | None:
    cleaned = text.strip().replace(",", "").replace("$", "")
    percent = cleaned.endswith("%")
    if percent:
        cleaned = cleaned[:-1]
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return (value / 100 if percent else value), ("percent" if percent else "number")


def extract_numeric(text: str) -> tuple[float | None, str, str | None]:
    candidates = list(_NUMBER.finditer(text or ""))
    if not candidates:
        return None, "no-number", None
    explicit = re.search(
        rf"(?:final answer(?:\s+is)?|answer is)\s*[:=]?\s*({_NUMBER.pattern})", text, re.I
    )
    selected = explicit or candidates[-1]
    parsed = _number(selected.group(1) if explicit else selected.group(0))
    if parsed is None:
        return None, "no-number", selected.group(0)
    value, kind = parsed
    return (
        float(value),
        (f"explicit-{kind}" if explicit else f"fallback-last-number-{kind}"),
        selected.group(0),
    )


def score_numeric(expected_text: str, actual_text: str) -> NumericScore:
    expected, _, _ = extract_numeric(expected_text)
    actual, method, extracted = extract_numeric(actual_text)
    if expected is None or actual is None:
        return NumericScore(False, None, None, expected, actual, method, extracted)
    absolute = abs(actual - expected)
    relative = absolute / abs(expected) if expected else (0.0 if absolute == 0 else None)
    _, _, expected_token = extract_numeric(expected_text)
    token = (expected_token or "").replace(",", "").replace("$", "")
    is_percent = token.endswith("%")
    digits = token[:-1] if is_percent else token
    decimals = len(digits.partition(".")[2])
    tolerance = Decimal(1).scaleb(-decimals) / 2
    if is_percent:
        tolerance /= 100
    tolerance += Decimal("1e-12")
    return NumericScore(
        Decimal(str(absolute)) <= tolerance, absolute, relative, expected, actual, method, extracted
    )


def score_dict(score: NumericScore) -> dict[str, object]:
    return asdict(score)
