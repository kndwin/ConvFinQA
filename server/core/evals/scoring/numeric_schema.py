from pydantic import BaseModel, ConfigDict, Field


class NumericScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exact_match: bool
    absolute_error: float | None
    relative_error: float | None
    expected: float | None
    actual: float | None
    extraction_method: str
    extracted_text: str | None
    selected_token: str | None = None
    candidate_details: list[dict[str, object]] = Field(default_factory=list)
    relative_tolerance: float = 0.01
