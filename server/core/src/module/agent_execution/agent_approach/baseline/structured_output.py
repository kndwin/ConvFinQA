"""Strict structured output contract for the baseline approach."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

_DECIMAL = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")


class StructuredAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["number", "boolean", "text", "unavailable"]
    value: str
    representation: Literal["raw", "percent"] | None = None
    scale: Literal["ones", "thousand", "million", "billion"] | None = None

    @model_validator(mode="after")
    def semantic_shape(self) -> StructuredAnswer:
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
