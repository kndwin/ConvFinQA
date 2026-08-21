import json
import unittest

from pydantic import ValidationError

from evals.benchmarks.convfinqa.cases import case_from_payload
from evals.benchmarks.convfinqa.cases_schema import ConversationCase, RawCase


def dialogue(**overrides):
    value = {
        "conv_questions": ["  first question  ", "second"],
        "conv_answers": [1],
    }
    value.update(overrides)
    return value


class ConvFinQACaseSchemaTests(unittest.TestCase):
    def test_local_normalization_and_conversion(self):
        case = case_from_payload(
            {
                "id": 7,
                "doc": {"pre_text": ["é"]},
                "dialogue": dialogue(
                    executed_answers=[None, 2], turn_program=["p", None], qa_split=[True, None]
                ),
                "features": {"unrelated": True},
            }
        )
        self.assertIsInstance(case, ConversationCase)
        self.assertEqual(case.dataset_id, "7")
        self.assertEqual(case.source_id, "7")
        self.assertEqual(case.document, json.dumps({"pre_text": ["é"]}, ensure_ascii=False))
        self.assertEqual(case.turns[0].question, "first question")
        self.assertIsNone(case.turns[1].answer)
        self.assertEqual(case.turns[1].executed_answer, "2")

    def test_db_json_forms_and_source_id(self):
        for dialogue_json in (dialogue(), json.dumps(dialogue())):
            with self.subTest(dialogue_json_type=type(dialogue_json).__name__):
                case = case_from_payload(
                    {
                        "id": "db",
                        "doc_json": {"table": {}},
                        "dialogue_json": dialogue_json,
                        "source_id": 42,
                    }
                )
                self.assertEqual(case.source_id, "42")
                self.assertEqual(case.document, '{"table": {}}')

        with self.assertRaisesRegex(ValueError, "dialogue JSON is invalid"):
            case_from_payload({"id": "db", "doc_json": "d", "dialogue_json": "{"})

    def test_local_dialogue_must_be_object(self):
        with self.assertRaisesRegex(ValueError, "dialogue"):
            case_from_payload({"id": "x", "doc": "d", "dialogue": json.dumps(dialogue())})

    def test_strict_optional_items_and_lengths(self):
        base = {"id": "x", "doc": "d", "dialogue": dialogue()}
        for name, value in (
            ("executed_answers", None),
            ("turn_program", None),
            ("qa_split", None),
            ("turn_program", [1, None]),
            ("qa_split", [1, None]),
        ):
            with self.subTest(name=name), self.assertRaisesRegex(ValidationError, name):
                RawCase.model_validate({**base, "dialogue": dialogue(**{name: value})})
        with self.assertRaisesRegex(ValueError, "length"):
            case_from_payload({**base, "dialogue": dialogue(qa_split=[True])})

    def test_question_and_id_validation(self):
        record = RawCase.model_validate({"id": 12, "doc": "d", "dialogue": dialogue()})
        self.assertEqual(record.id, "12")
        self.assertEqual(record.dialogue.conv_questions[0], "first question")
        for invalid in (None, " ", True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                RawCase.model_validate({"id": invalid, "doc": "d", "dialogue": dialogue()})


if __name__ == "__main__":
    unittest.main()
