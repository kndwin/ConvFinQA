"""Strict structured output contract for program-of-thought."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class ProgramNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal[
        "evidence", "prior", "constant", "add", "subtract", "multiply", "divide", "greater", "exp"
    ]
    args: list[ProgramNode] | None = None
    id: str | None = None
    turn: int | None = None

    @model_validator(mode="after")
    def semantic_shape(self) -> ProgramNode:
        binary = {"add", "subtract", "multiply", "divide", "greater", "exp"}
        if self.op in {"evidence", "constant"}:
            if self.args is not None or self.turn is not None or self.id is None:
                raise ValueError("evidence/constant leaves require only id")
        elif self.op == "prior":
            if self.args is not None or self.id is not None or self.turn is None:
                raise ValueError("prior leaves require only turn")
        elif self.op in binary and (
            self.id is not None or self.turn is not None or self.args is None or len(self.args) != 2
        ):
            raise ValueError("operations require exactly two args")
        return self


ProgramNode.model_rebuild()
