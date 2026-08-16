import unittest
from typing import cast

from evals.golden import build_golden
from evals.runner import _event_text
from evals.scoring import extract_numeric, score_numeric


class GoldenTests(unittest.TestCase):
    def test_builds_conversational_golden_with_metadata(self):
        golden = build_golden(
            {
                "id": 3139,
                "doc_json": "table",
                "dialogue_json": (
                    '{"conv_questions":["Q1"],"conv_answers":["14.1%"],"turn_program":["x"],"executed_answers":["14.1%"]}'
                ),
            }
        )
        metadata = cast(dict[str, object], golden.additional_metadata)
        self.assertIsNone(golden.turns)
        self.assertIn("Q1 -> expected answer: 14.1%", cast(str, golden.expected_outcome))
        self.assertEqual(metadata["programs"], ["x"])
        self.assertEqual(metadata["executed_answers"], ["14.1%"])
        self.assertEqual(golden.context, ["table"])


class NumericScoringTests(unittest.TestCase):
    def test_decimal_percentage_equivalence(self):
        self.assertTrue(score_numeric("14.1%", "The final answer is 0.141").exact_match)
        self.assertTrue(score_numeric("-8.9%", "Answer is -8.94%").exact_match)

    def test_currency_commas_and_wrong_sign(self):
        self.assertTrue(score_numeric("$1,234.50", "Final answer: 1,234.5").exact_match)
        self.assertFalse(score_numeric("8.9%", "Final answer: -8.9%").exact_match)

    def test_display_precision_boundaries(self):
        self.assertTrue(score_numeric("-8.9%", "Answer is -8.94%").exact_match)
        self.assertFalse(score_numeric("206588", "Final answer: 207588").exact_match)
        self.assertTrue(score_numeric("1234.50", "Final answer: 1234.504").exact_match)
        self.assertFalse(score_numeric("1234.50", "Final answer: 1234.506").exact_match)

    def test_explicit_final_answer_beats_other_numbers(self):
        actual, method, _ = extract_numeric("I used 3 steps and 40 rows. Final answer: 14.1%.")
        self.assertEqual(actual, 0.141)
        self.assertTrue(method.startswith("explicit"))
        self.assertTrue(extract_numeric("The final answer is 14.1%.")[1].startswith("explicit"))

    def test_fallback_last_number_and_no_number(self):
        actual, method, _ = extract_numeric("The calculation uses 12 and produces 14.1%")
        self.assertEqual(actual, 0.141)
        self.assertTrue(method.startswith("fallback-last-number"))
        self.assertEqual(extract_numeric("No numeric answer")[1], "no-number")


class StreamEventTests(unittest.TestCase):
    def test_only_collects_assistant_text_events(self):
        self.assertEqual(
            _event_text({"type": "TEXT_MESSAGE_CONTENT", "delta": "Final answer: 90"}),
            "Final answer: 90",
        )
        self.assertEqual(_event_text({"type": "TOOL_CALL_ARGS", "delta": '{"a":90,"b":0}'}), "")
        self.assertEqual(_event_text({"type": "TOOL_CALL_RESULT", "content": "90.0"}), "")


if __name__ == "__main__":
    unittest.main()
