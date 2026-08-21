from typing import Any

from evals.benchmarks.convfinqa.cases_schema import ConversationCase, ExpectedTurn, RawCase


def case_from_payload(payload: dict[str, Any]) -> ConversationCase:
    record = RawCase.model_validate(payload)
    dialogue = record.dialogue
    questions = dialogue.conv_questions
    answers = dialogue.conv_answers
    turns = []
    for index, question in enumerate(questions):
        answer = answers[index] if index < len(answers) else None
        turns.append(
            ExpectedTurn(
                question=question.strip(),
                answer=None if answer is None else str(answer),
                executed_answer=(
                    None
                    if dialogue.executed_answers is None or dialogue.executed_answers[index] is None
                    else str(dialogue.executed_answers[index])
                ),
                turn_program=(
                    dialogue.turn_program[index] if dialogue.turn_program is not None else None
                ),
                qa_split=(dialogue.qa_split[index] if dialogue.qa_split is not None else None),
            )
        )
    return ConversationCase(
        dataset_id=record.id,
        document=record.document,
        turns=tuple(turns),
        source_id=(
            record.id
            if record.is_local
            else (None if record.source_id is None else str(record.source_id))
        ),
    )
