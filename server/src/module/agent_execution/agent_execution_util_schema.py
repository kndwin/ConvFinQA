"""Private Pydantic schemas used to normalize AG-UI messages."""

from pydantic import BaseModel, ConfigDict


class _TextContentPart(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    text: str = ""


class _ExecutionMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: str | int | None = None
    role: str
    content: str | list[_TextContentPart] = ""
