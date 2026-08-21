"""Pydantic schemas for ConvFinQA source records and conversation cases."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class RawDialogue(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    conv_questions: list[str] = Field(min_length=1)
    conv_answers: list[Any]
    executed_answers: list[Any] | None = None
    turn_program: list[str | None] | None = None
    qa_split: list[bool | None] | None = None

    @field_validator("conv_questions", mode="before")
    @classmethod
    def strict_questions(cls, value: Any) -> list[str]:
        if type(value) is not list or not value:
            raise ValueError("conv_questions must be a non-empty list")
        result: list[str] = []
        for question in value:
            if type(question) is not str or not question.strip():
                raise ValueError("each ConvFinQA question must be a non-empty string")
            result.append(question.strip())
        return result

    @field_validator("conv_answers", "executed_answers", "turn_program", "qa_split", mode="before")
    @classmethod
    def strict_lists(cls, value: Any, info: ValidationInfo) -> list[Any]:
        # Missing optional fields use their defaults and skip this validator;
        # fields explicitly supplied as null must still be rejected.
        if type(value) is not list:
            raise ValueError(f"{info.field_name} must be a list")
        return value

    @field_validator("turn_program", mode="before")
    @classmethod
    def strict_programs(cls, value: Any) -> list[str | None] | None:
        if value is not None and type(value) is not list:
            raise ValueError("turn_program must be a list")
        if value is not None and any(item is not None and type(item) is not str for item in value):
            raise ValueError("turn_program values must be strings or null")
        return value

    @field_validator("qa_split", mode="before")
    @classmethod
    def strict_splits(cls, value: Any) -> list[bool | None] | None:
        if value is not None and type(value) is not list:
            raise ValueError("qa_split must be a list")
        if value is not None and any(item is not None and type(item) is not bool for item in value):
            raise ValueError("qa_split values must be booleans or null")
        return value

    @model_validator(mode="after")
    def matching_metadata_lengths(self) -> RawDialogue:
        for name in ("executed_answers", "turn_program", "qa_split"):
            value = getattr(self, name)
            if value is not None and len(value) != len(self.conv_questions):
                raise ValueError(
                    f"{name} length ({len(value)}) must match "
                    f"conv_questions length ({len(self.conv_questions)})"
                )
        return self


class RawCase(BaseModel):
    """Canonicalized raw record, while retaining unrelated source fields."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    document: str
    dialogue: RawDialogue
    source_id: Any = None
    is_local: bool = Field(exclude=True)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: Any) -> str:
        if type(value) not in (str, int) or not str(value).strip():
            raise ValueError("ConvFinQA record id must be a non-empty string or integer")
        return str(value)

    @model_validator(mode="before")
    @classmethod
    def normalize_source_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            raise ValueError("ConvFinQA record must be an object")

        data = dict(value)
        is_local = "dialogue" in data
        if is_local:
            if "doc" not in data:
                raise ValueError("local ConvFinQA record must contain a doc object or string")
            raw_dialogue = data["dialogue"]
        else:
            if "dialogue_json" not in data:
                raise ValueError("ConvFinQA record must contain dialogue or dialogue_json")
            raw_dialogue = data["dialogue_json"]
            if isinstance(raw_dialogue, str):
                try:
                    raw_dialogue = json.loads(raw_dialogue)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"dialogue JSON is invalid: {exc.msg}") from exc
        if not isinstance(raw_dialogue, dict):
            raise ValueError("ConvFinQA dialogue must be a JSON object")

        if "doc_json" not in data and "doc" not in data:
            raise ValueError("ConvFinQA record must contain doc or doc_json")
        document = data.get("doc_json", data.get("doc"))
        if isinstance(document, dict):
            document = json.dumps(document, ensure_ascii=False)
        elif not isinstance(document, str):
            raise ValueError("ConvFinQA document must be a string or object")

        data.update(document=document, dialogue=raw_dialogue, is_local=is_local)
        return data


class ExpectedTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=1)
    answer: str | None = None
    executed_answer: str | None = None
    turn_program: str | None = None
    qa_split: bool | None = None


class ConversationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(min_length=1)
    document: str
    turns: tuple[ExpectedTurn, ...] = Field(min_length=1)
    source_id: str | None = None
