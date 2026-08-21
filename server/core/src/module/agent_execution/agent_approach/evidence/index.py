"""Stable, production-owned ConvFinQA evidence index."""

# The compact index format is intentionally kept close to its deterministic schema.
import hashlib
import json
import re
from contextlib import suppress
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict

INDEX_VERSION = "evidence-index:v1"


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    kind: Literal["table", "narrative"]
    text: str
    provenance: str
    numeric: str | None = None
    scale: Literal["ones", "thousand", "million", "billion"] | None = None
    representation: Literal["raw", "percent"] | None = None


def parse_decimal(value: object) -> str | None:
    text = str(value).strip()
    if text.endswith("%"):
        text = text[:-1]
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("() $").replace(",", "")
    with suppress(InvalidOperation, ValueError):
        parsed = Decimal(text)
        return format(-parsed if negative else parsed, "f")
    return None


def index_document(document: str | dict) -> tuple[EvidenceItem, ...]:
    obj = json.loads(document) if isinstance(document, str) else document
    if not isinstance(obj, dict):
        raise ValueError("document must be an object")
    out: list[EvidenceItem] = []
    table = obj.get("table", {})
    if isinstance(table, dict):
        for ri, (row, cells) in enumerate(table.items()):
            if isinstance(cells, dict):
                for ci, (col, raw) in enumerate(cells.items()):
                    label = f"{row} {col}".lower()
                    scale = next(
                        (s for s in ("billion", "million", "thousand") if s in label), None
                    )
                    rep = "percent" if "%" in label or "%" in str(raw) else "raw"
                    out.append(
                        EvidenceItem(
                            id=f"t:r{ri}:c{ci}",
                            kind="table",
                            text=f"{row} | {col} | {raw}",
                            provenance=f"table[{row!r}][{col!r}]",
                            numeric=parse_decimal(raw),
                            scale=scale,
                            representation=rep,
                        )
                    )
    for section in ("pre_text", "post_text"):
        text = str(obj.get(section, "")).strip()
        for i, sentence in enumerate(re.split(r"(?<=[.!?])\s+", text) if text else ()):
            if not sentence:
                continue
            base = f"n:{section[:1]}{i}"
            out.append(
                EvidenceItem(id=base, kind="narrative", text=sentence, provenance=f"{section}[{i}]")
            )
            for j, token in enumerate(
                re.findall(r"(?<![\w.])(?:\(?[$]?[-+]?\d[\d,]*(?:\.\d+)?%?\)?)", sentence)
            ):
                out.append(
                    EvidenceItem(
                        id=f"{base}:v{j}",
                        kind="narrative",
                        text=f"{sentence} (numeric span: {token})",
                        provenance=f"{section}[{i}].span[{j}]",
                        numeric=parse_decimal(token),
                        scale="ones",
                        representation="percent" if token.endswith("%") else "raw",
                    )
                )
    return tuple(out)


def index_hash(index: tuple[EvidenceItem, ...]) -> str:
    return hashlib.sha256(
        json.dumps([x.model_dump() for x in index], sort_keys=True).encode()
    ).hexdigest()
