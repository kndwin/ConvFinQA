from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_ids: tuple[str, ...] = ()
    targets: tuple[str, ...] = Field(min_length=1)
    application_model: str = Field(default="gpt-5.6-luna", min_length=1)
    dataset_path: str | None = None
    split: str | None = None
    record_limit: int | None = Field(default=None, gt=0)

    @field_validator("dataset_ids", mode="before")
    @classmethod
    def valid_ids(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, (str, int)):
            value = (value,)
        if not isinstance(value, (tuple, list)):
            raise ValueError("dataset IDs must be a list or tuple")
        result = tuple(str(item).strip() for item in value)
        if any(not item for item in result):
            raise ValueError("dataset IDs must not be empty")
        return result
