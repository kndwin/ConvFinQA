import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

from inspect_ai import eval
from inspect_ai.log import read_eval_log

from evals.benchmarks.convfinqa.task import build_task
from evals.config_schema import EvaluationConfig
from evals.convfinqa import case_from_payload
from evals.direct_schema import ObservedTurn
from evals.events import EventCollector
from evals.events_schema import ModelUsageObservation
from evals.plan import main
from evals.scoring import contains_text, extract_numeric, score_numeric


def case():
    return case_from_payload(
        {
            "id": 4,
            "doc_json": "doc",
            "dialogue_json": {
                "conv_questions": ["first?", "second?"],
                "conv_answers": ["10", "20"],
            },
        }
    )


async def direct_stub(case, target, config):
    del target, config
    return tuple(
        ObservedTurn(
            turn=index,
            question=turn.question,
            expected=turn.answer,
            actual=f"Final answer: {turn.answer}",
            latency_seconds=0,
            run_id=f"r{index}",
            thread_id="thread",
        )
        for index, turn in enumerate(case.turns, 1)
    )


class NumericTests(unittest.TestCase):
    def test_numeric_normalization_and_tolerance(self):
        self.assertTrue(score_numeric("14.1%", "Final answer: 0.141").exact_match)
        self.assertTrue(score_numeric("48.9%", "49.0% ... 2008 ... 2009").exact_match)
        self.assertEqual(score_numeric("48.9%", "49.0% ... 2008 ... 2009").selected_token, "49.0%")
        self.assertTrue(score_numeric("48.9%", "48.98% ... 2008/2009").exact_match)
        self.assertTrue(score_numeric("2.4", "$2.4 million ... 2008 ... 2009").exact_match)
        self.assertEqual(
            score_numeric("2.4", "$2.4 million ... 2008 ... 2009").selected_token,
            "$2.4 million",
        )
        self.assertTrue(score_numeric("74.33", "74.3").exact_match)
        self.assertTrue(score_numeric("$1,234.50", "Answer is 1,234.504").exact_match)
        self.assertTrue(score_numeric("1234.50", "Answer is 1234.506").exact_match)
        self.assertFalse(score_numeric("100", "Answer is 102").exact_match)
        self.assertFalse(score_numeric("8.9%", "Answer is -8.9%").exact_match)

    def test_numeric_candidate_priority_and_kinds(self):
        self.assertFalse(score_numeric("90", "90 was intermediate; Final answer: 12").exact_match)
        self.assertTrue(score_numeric("48.9%", "0.489").exact_match)
        self.assertTrue(score_numeric("−8.9", "−8.9").exact_match)

    def test_explicit_answer_wins_and_missing_number_fails(self):
        value, method, _ = extract_numeric("Used 3 rows. Final answer: 14.1%")
        self.assertEqual(value, 0.141)
        self.assertEqual(method, "explicit-percent")
        self.assertEqual(extract_numeric("unknown")[1], "no-number")


class ContainsTests(unittest.TestCase):
    def test_evalite_literal_contains_edge_cases(self):
        self.assertTrue(contains_text("90", "The result is $90 million."))
        self.assertFalse(contains_text("74.33", "The result is 74.3."))
        self.assertFalse(contains_text("48.9%", "The result is 48.98%."))
        # This is intentionally a known false positive of substring scoring.
        self.assertTrue(contains_text("90", "Used 90 in an intermediate calculation; final: 12."))
        self.assertFalse(contains_text(None, "90"))
        self.assertFalse(contains_text("", "anything"))


class DataAndEventTests(unittest.TestCase):
    def test_malformed_case_is_rejected(self):
        with self.assertRaises(ValueError):
            case_from_payload({"id": 1, "dialogue_json": {"conv_questions": "bad"}})

    def test_collector_keeps_tools(self):
        collector = EventCollector()
        for event in (
            {"type": "TOOL_CALL_START", "tool_call_id": "t", "tool_call_name": "calc"},
            {"type": "TOOL_CALL_ARGS", "tool_call_id": "t", "delta": '{"x":1}'},
            {"type": "TOOL_CALL_RESULT", "tool_call_id": "t", "content": "1"},
            {"type": "TEXT_MESSAGE_CONTENT", "delta": "Answer is 1"},
        ):
            collector.add(event)
        self.assertEqual("".join(collector.text), "Answer is 1")
        self.assertEqual(collector.tools[0].name, "calc")
        self.assertEqual(collector.tools[0].result, "1")

    def test_application_usage_is_collected_and_missing_stays_unknown(self):
        collector = EventCollector()
        collector.add(
            {
                "type": "CUSTOM",
                "name": "model_usage",
                "value": {
                    "calls": [
                        {
                            "model": "application-model",
                            "input_tokens": 4,
                            "output_tokens": 2,
                            "total_tokens": 6,
                        }
                    ]
                },
            }
        )
        self.assertEqual(collector.model_usage[0].model, "application-model")
        self.assertEqual(collector.model_usage[0].total_tokens, 6)
        self.assertEqual(EventCollector().model_usage, ())

    def test_collector_appends_multiple_usage_events(self):
        collector = EventCollector()
        collector.add(
            {
                "type": "CUSTOM",
                "name": "model_usage",
                "value": {
                    "calls": [
                        {"model": "m", "input_tokens": 4, "output_tokens": 2, "total_tokens": 7}
                    ]
                },
            }
        )
        collector.add(
            {
                "type": "CUSTOM",
                "name": "model_usage",
                "value": {
                    "calls": [
                        {"model": "m", "input_tokens": 3, "output_tokens": 1, "total_tokens": 5}
                    ]
                },
            }
        )
        self.assertEqual(len(collector.model_usage), 2)
        self.assertEqual(sum(item.input_tokens for item in collector.model_usage), 7)
        self.assertEqual(sum(item.output_tokens for item in collector.model_usage), 3)
        self.assertEqual(sum(item.total_tokens for item in collector.model_usage), 12)


class InspectTests(unittest.TestCase):
    def test_record_limit_balances_approaches_before_expansion(self):
        config = EvaluationConfig(
            targets=("baseline:v1", "baseline-tool:v1", "program-of-thought:v1"),
            record_limit=2,
        )
        task = build_task((case(), case().model_copy(update={"dataset_id": "5"})), config)
        self.assertEqual(len(task.dataset), 6)
        self.assertEqual(
            [
                sum(sample.metadata["approach"] == target for sample in task.dataset)
                for target in config.targets
            ],
            [2, 2, 2],
        )

    def test_record_limit_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            EvaluationConfig(targets=("baseline:v1",), record_limit=0)

    def test_static_no_model_run_writes_readable_log(self):
        config = EvaluationConfig(dataset_ids=(4,), targets=("baseline:v1",))
        with patch("evals.benchmarks.convfinqa.task.execute_direct", new=direct_stub):
            task = build_task((case(),), config)
            self.assertIsNone(task.model)
            with tempfile.TemporaryDirectory() as directory:
                logs = eval(task, model=None, log_dir=directory, display="none")
                files = list(Path(directory).glob("*.eval"))
                self.assertEqual(len(files), 1)
                log = read_eval_log(str(files[0]))
        self.assertEqual(log.status, "success")
        self.assertEqual(len(logs), 1)
        samples = log.samples
        assert samples is not None
        sample = samples[0]
        self.assertEqual(
            [message.role for message in sample.messages],
            ["user", "assistant", "user", "assistant"],
        )
        scores = sample.scores
        assert scores is not None
        self.assertEqual(
            set(scores),
            {
                "turn_execution_accuracy",
                "conversation_exact_accuracy",
                "parse_failure_rate",
                "numeric_accuracy",
                "contains_accuracy",
            },
        )
        self.assertEqual(scores["numeric_accuracy"].value, 1.0)
        self.assertEqual(scores["contains_accuracy"].value, 1.0)
        metadata = scores["contains_accuracy"].metadata
        assert metadata is not None
        self.assertTrue(metadata["fully_correct_conversation"])
        self.assertEqual([turn["contains"] for turn in metadata["turns"]], [True, True])
        self.assertEqual(
            [(turn["turn"], turn["expected"], turn["actual"]) for turn in metadata["turns"]],
            [(1, "10", "Final answer: 10"), (2, "20", "Final answer: 20")],
        )

    def test_external_usage_is_serialized_without_a_provider_call(self):
        async def usage_stub(case, target, config):
            observations = await direct_stub(case, target, config)
            return tuple(
                observation.model_copy(
                    update={
                        "model_usage": (
                            ModelUsageObservation(
                                model="gpt-test", input_tokens=7, output_tokens=3, total_tokens=10
                            ),
                            ModelUsageObservation(
                                model="gpt-test", input_tokens=2, output_tokens=1, total_tokens=3
                            ),
                        )
                    }
                )
                for observation in observations
            )

        config = EvaluationConfig(dataset_ids=(4,), targets=("baseline:v1",))
        with patch("evals.benchmarks.convfinqa.task.execute_direct", new=usage_stub):
            task = build_task((case(),), config)
            with tempfile.TemporaryDirectory() as directory:
                eval(task, model=None, log_dir=directory, display="none")
                log = read_eval_log(str(next(Path(directory).glob("*.eval"))))
        assert log.samples is not None
        sample = log.samples[0]
        assert sample.model_usage is not None
        self.assertEqual(sample.model_usage["gpt-test"].input_tokens, 18)
        self.assertEqual(sample.model_usage["gpt-test"].output_tokens, 8)
        self.assertEqual(sample.model_usage["gpt-test"].total_tokens, 26)
        self.assertEqual(
            sample.model_usage["gpt-test"].model_dump(),
            {
                "input_tokens": 18,
                "output_tokens": 8,
                "total_tokens": 26,
                "input_tokens_cache_write": None,
                "input_tokens_cache_read": None,
                "reasoning_tokens": None,
                "total_cost": None,
            },
        )

    def test_static_log_contains_grouped_metrics_for_each_scorer(self):
        config = EvaluationConfig(
            targets=("baseline:v1", "baseline-tool:v1", "program-of-thought:v1"),
            record_limit=2,
        )
        cases = (case(), case().model_copy(update={"dataset_id": "5"}))
        with patch("evals.benchmarks.convfinqa.task.execute_direct", new=direct_stub):
            task = build_task(cases, config)
            with tempfile.TemporaryDirectory() as directory:
                eval(task, model=None, log_dir=directory, display="none")
                log = read_eval_log(str(next(Path(directory).glob("*.eval"))))
        self.assertEqual(len(log.samples or []), 6)
        assert log.results is not None
        for result in log.results.scores:
            # Parse-failure rate is correctly zero for this successful fixture;
            # correctness scorers are one.
            self.assertIn(result.metrics["mean"].value, (0.0, 1.0))
            self.assertEqual(result.metrics["stderr"].value, 0.0)
            for target in config.targets:
                self.assertIn(result.metrics[f"{target}_mean"].value, (0.0, 1.0))
                self.assertEqual(result.metrics[f"{target}_stderr"].value, 0.0)

    def test_planner_mocked_success_and_invalid_exit_two(self):
        with patch("evals.cli.plan.load_cases_async", new=AsyncMock(return_value=(case(),))):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["convfinqa", "--targets", "baseline:v1"]), 0)
            self.assertIn('"samples": 1', output.getvalue())
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(main(["convfinqa", "--dataset-ids", "0"]), 2)


if __name__ == "__main__":
    unittest.main()
