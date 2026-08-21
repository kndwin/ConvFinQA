import json
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field


class CandidateQuestionAnswer(BaseModel):
    question: str
    answer: str | None


def candidate_qa_from_dialogue_json(dialogue_json: str) -> list[CandidateQuestionAnswer]:
    """Extract the raw ConvFinQA candidate Q&A pairs without trusting the payload shape."""
    try:
        payload: Any = json.loads(dialogue_json)
    except TypeError, json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    questions = payload.get("conv_questions")
    answers = payload.get("conv_answers")
    if not isinstance(questions, list):
        return []
    if not isinstance(answers, list):
        answers = []

    candidates: list[CandidateQuestionAnswer] = []
    for index, question in enumerate(questions):
        if not isinstance(question, str) or not question.strip():
            continue
        answer = answers[index] if index < len(answers) else None
        normalized_answer = answer.strip() if isinstance(answer, str) else None
        candidates.append(
            CandidateQuestionAnswer(
                question=question.strip(),
                answer=normalized_answer or None,
            )
        )
    return candidates


class DatasetConversationResponse(BaseModel):
    """Public representation of a stored dataset_conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None
    source_id: str
    split: str
    pre_text: str
    post_text: str
    num_dialogue_turns: int | None
    has_type2_question: bool | None
    has_duplicate_columns: bool | None
    has_non_numeric_values: bool | None
    features_json: str
    doc_json: str | None
    dialogue_json: str

    @computed_field
    @property
    def candidate_qa(self) -> list[CandidateQuestionAnswer]:
        """Extract candidate questions from the stored dialogue payload."""
        return candidate_qa_from_dialogue_json(self.dialogue_json)
