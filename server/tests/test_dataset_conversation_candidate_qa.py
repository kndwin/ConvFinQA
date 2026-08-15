import unittest

from src.module.dataset_conversations.dataset_conversations_router_schema import (
    candidate_qa_from_dialogue_json,
)


class CandidateQuestionAnswerTests(unittest.TestCase):
    def test_maps_pairs_by_question_index_and_trims_text(self):
        result = candidate_qa_from_dialogue_json(
            '{"conv_questions": [" Q1 ", "Q2", " ", 4], "conv_answers": [" A1 ", " A2 ", "extra"]}'
        )
        self.assertEqual(
            [(item.question, item.answer) for item in result], [("Q1", "A1"), ("Q2", "A2")]
        )

    def test_missing_and_non_string_answers_are_unavailable(self):
        result = candidate_qa_from_dialogue_json(
            '{"conv_questions": ["Q1", "Q2", "Q3"], "conv_answers": [4, "  "]}'
        )
        self.assertEqual(
            [(item.question, item.answer) for item in result],
            [("Q1", None), ("Q2", None), ("Q3", None)],
        )

    def test_missing_answers_array_keeps_questions(self):
        result = candidate_qa_from_dialogue_json('{"conv_questions": ["Q1"]}')
        self.assertEqual([(item.question, item.answer) for item in result], [("Q1", None)])

    def test_invalid_or_wrong_shape_is_empty(self):
        for payload in ("not json", "[]", "null", "{}", '{"conv_questions": "Q"}'):
            with self.subTest(payload=payload):
                self.assertEqual(candidate_qa_from_dialogue_json(payload), [])


if __name__ == "__main__":
    unittest.main()
