from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    kind: Literal["table", "narrative"]
    text: str
    provenance: str
    raw: Any = None
    numeric: str | None = None
    scale: Literal["ones", "thousand", "million", "billion"] | None = None
    representation: Literal["raw", "percent"] | None = None
