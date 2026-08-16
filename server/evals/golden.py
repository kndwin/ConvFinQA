import json
from typing import Any

from deepeval.dataset import ConversationalGolden


def _payload(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except TypeError, json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_golden(dataset: dict[str, Any]) -> ConversationalGolden:
    """Build one DeepEval golden while preserving the source conversation."""
    dialogue = _payload(dataset.get("dialogue_json", ""))
    questions = dialogue.get("conv_questions", [])
    answers = dialogue.get("conv_answers", [])
    programs = dialogue.get(
        "turn_program", dialogue.get("conv_programs", dialogue.get("programs", []))
    )
    executed = dialogue.get("executed_answers", dialogue.get("conv_executed_answers", []))
    if not isinstance(questions, list):
        questions = []
    if not isinstance(answers, list):
        answers = []
    if not isinstance(programs, list):
        programs = []
    if not isinstance(executed, list):
        executed = []

    pairs = [
        (question.strip(), answers[index] if index < len(answers) else None)
        for index, question in enumerate(questions)
        if isinstance(question, str) and question.strip()
    ]
    expected = "\n".join(
        f"Turn {index}: {question} -> expected answer: {answer}"
        for index, (question, answer) in enumerate(pairs, 1)
    )
    return ConversationalGolden(
        scenario=f"ConvFinQA dataset conversation {dataset.get('id')}",
        expected_outcome=expected or "No questions in this conversation.",
        context=[str(dataset.get("doc_json", ""))],
        additional_metadata={
            "dataset_id": dataset.get("id"),
            "questions": [question for question, _ in pairs],
            "answers": [answer for _, answer in pairs],
            "executed_answers": executed,
            "programs": programs,
            "turn_program": programs,
            "source_id": dataset.get("source_id"),
        },
    )


def golden_shape(golden: ConversationalGolden) -> dict[str, Any]:
    return golden.model_dump(mode="json", by_alias=True, exclude_none=False)
