import unittest

from inspect_ai.solver import TaskState

from evals.benchmarks.convfinqa.scorers import (
    _text_answer,
    conversation_exact_accuracy,
    parse_failure_rate,
    turn_execution_accuracy,
)
from evals.direct_schema import ObservedTurn
from evals.scoring.numeric import score_numeric, score_numeric_execution


class ExecutionScoringTests(unittest.TestCase):
    def test_strict_tolerance_boundary_and_legacy_compatibility(self):
        self.assertTrue(score_numeric_execution("100", "100.0099").exact_match)
        self.assertFalse(score_numeric_execution("100", "100.0101").exact_match)
        self.assertTrue(score_numeric_execution("0", "0.000009").exact_match)
        self.assertFalse(score_numeric_execution("0", "0.000011").exact_match)
        self.assertTrue(score_numeric("100", "100.5").exact_match)

    def test_percent_and_requested_unit_equivalence(self):
        self.assertTrue(score_numeric_execution("14.1%", "0.141").exact_match)
        self.assertTrue(
            score_numeric_execution("2200", "$2.2 billion", "expressed in millions").exact_match
        )

    def test_boolean_and_text_normalization(self):
        self.assertEqual(_text_answer("Yes", "Final answer: YES"), (True, True, "yes"))
        self.assertEqual(
            _text_answer("Revenue", "The final answer is: revenue. It increased."),
            (True, True, "revenue"),
        )
        self.assertEqual(_text_answer("Yes", "The answer is yes!"), (True, True, "yes"))
        self.assertEqual(_text_answer("Revenue", ""), (False, False, ""))


def _observation(turn: int, expected: str, actual: str, *, executed: str | None = None) -> dict:
    return ObservedTurn(
        turn=turn,
        question="What is the answer?",
        expected=expected,
        executed_answer=executed,
        actual=actual,
        latency_seconds=0,
        run_id=f"run-{turn}",
        thread_id="thread",
    ).model_dump(mode="json")


def _state(*observations: dict) -> TaskState:
    return TaskState(
        model="test",
        sample_id="sample",
        epoch=1,
        input="question",
        messages=[],
        metadata={"observations": list(observations)},
    )


class ExecutionScorerTests(unittest.IsolatedAsyncioTestCase):
    async def test_turn_scorer_prioritizes_explicit_final_answer(self):
        score = await turn_execution_accuracy()(
            _state(_observation(1, "10", "The intermediate value was 99. Final answer: 10.")), None
        )
        self.assertEqual(score.value, 1.0)

    async def test_turn_scorer_uses_fallback_final_candidate(self):
        score = await turn_execution_accuracy()(
            _state(_observation(1, "10", "The calculation gives 10.")), None
        )
        self.assertEqual(score.value, 1.0)

    async def test_parse_failure_is_distinct_from_parsed_wrong_answer(self):
        state = _state(
            _observation(1, "10", "Final answer: 11"), _observation(2, "10", "No result.")
        )
        execution = await turn_execution_accuracy()(state, None)
        failures = await parse_failure_rate()(state, None)
        self.assertEqual(execution.value, 0.0)
        self.assertEqual(failures.value, 0.5)
        self.assertEqual(execution.metadata["turns"][0]["usable_answer"], True)
        self.assertEqual(execution.metadata["turns"][1]["usable_answer"], False)

    async def test_one_wrong_turn_makes_conversation_inexact(self):
        state = _state(
            _observation(1, "10", "Final answer: 10"),
            _observation(2, "20", "Final answer: 21"),
        )
        score = await conversation_exact_accuracy()(state, None)
        self.assertEqual(score.value, 0.0)

    async def test_boolean_and_text_scorer_values(self):
        state = _state(
            _observation(1, "yes", "Final answer: YES!"),
            _observation(2, "Revenue", "The final answer is Revenue. It grew."),
        )
        score = await turn_execution_accuracy()(state, None)
        self.assertEqual(score.value, 1.0)


if __name__ == "__main__":
    unittest.main()
