"""Strict structured output contracts for the evidence approach."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

_DECIMAL = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")


class EvidenceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_ids: list[str]


class EvidenceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["number", "boolean", "text", "unavailable"]
    value: str
    representation: Literal["raw", "percent"] | None = None
    scale: Literal["ones", "thousand", "million", "billion"] | None = None
    result_ref: str | None

    @model_validator(mode="after")
    def semantic_shape(self) -> EvidenceAnswer:
        if self.kind == "number":
            if (
                self.representation is None
                or self.scale is None
                or not _DECIMAL.fullmatch(self.value)
            ):
                raise ValueError("numbers require a lexical decimal, representation, and scale")
        else:
            if self.representation is not None or self.scale is not None:
                raise ValueError("non-numbers require null representation and scale")
            if self.kind == "boolean" and self.value not in {"true", "false"}:
                raise ValueError("boolean value must be true or false")
        return self

    @model_validator(mode="after")
    def grounded_shape(self) -> EvidenceAnswer:
        if self.kind == "number" and not self.result_ref:
            raise ValueError("numeric evidence answers require result_ref")
        if self.kind != "number" and self.result_ref is not None:
            raise ValueError("result_ref is only valid for numeric answers")
        return self
