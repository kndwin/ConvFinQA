import hashlib
import json
import unittest
from pathlib import Path

import yaml

from evals.benchmarks.convfinqa.sources import load_cases
from evals.benchmarks.convfinqa.task import build_task
from evals.config_schema import EvaluationConfig
from evals.scoring.numeric import score_numeric
from evals.targets import resolve_target

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "configs" / "convfinqa-2026-08-20-30-v2.yaml"
TASK_CONFIG = yaml.safe_load(CONFIG.read_text())
IDS = tuple(TASK_CONFIG["dataset_ids"])
TARGETS = ("baseline:v2", "baseline-tool:v2", "program-of-thought:v2")


class V2PromptTests(unittest.TestCase):
    def test_v1_defaults_and_hashes_are_unchanged(self):
        expected = {
            "baseline:v1": "ea4f7d1b3e2a6528b7603be47ac7519cc1653c6581090ba4dcfcca93c4ee7748",
            "baseline-tool:v1": "2a734856a18e9c3212396b045e3ca8b058712953a1ef1d22cf85e03c0bcf9394",
            "program-of-thought:v1": (
                "6aafd5de758a167ffef1d6edecae127a3d80ac369d758175321acf2dbcb3e02a"
            ),
        }
        for target_id, digest in expected.items():
            prompt = resolve_target(target_id).prompt
            self.assertEqual(prompt.id, target_id)
            self.assertEqual(prompt.content_hash, digest)
            self.assertEqual(hashlib.sha256(prompt.instructions.encode()).hexdigest(), digest)

    def test_v2_resolution_and_hashes(self):
        for target_id in TARGETS:
            prompt = resolve_target(target_id).prompt
            self.assertEqual(prompt.id, target_id)
            self.assertEqual(
                prompt.content_hash,
                hashlib.sha256(prompt.instructions.encode()).hexdigest(),
            )
            self.assertIs(resolve_target(target_id).prompt, prompt)


class MetadataAndScorerTests(unittest.TestCase):
    def test_metadata_preservation_and_legacy_fallback(self):
        from evals.convfinqa import case_from_payload

        case = case_from_payload(
            {
                "id": "x",
                "doc": "d",
                "dialogue": {
                    "conv_questions": ["q"],
                    "conv_answers": ["display"],
                    "executed_answers": ["0.18"],
                    "turn_program": ["divide(18, const_100)"],
                    "qa_split": [True],
                },
            }
        )
        turn = case.turns[0]
        self.assertEqual(
            (turn.answer, turn.executed_answer, turn.qa_split), ("display", "0.18", True)
        )
        self.assertEqual(turn.turn_program, "divide(18, const_100)")
        legacy = case_from_payload(
            {"id": "y", "doc": "d", "dialogue": {"conv_questions": ["q"], "conv_answers": ["a"]}}
        )
        self.assertIsNone(legacy.turns[0].executed_answer)

    def test_metadata_arrays_are_actionably_validated(self):
        from evals.convfinqa import case_from_payload

        base = {"id": "x", "doc": "d", "dialogue": {"conv_questions": ["q"], "conv_answers": ["a"]}}
        for name, value in (
            ("executed_answers", []),
            ("turn_program", "bad"),
            ("qa_split", ["a", "b"]),
        ):
            payload = json.loads(json.dumps(base))
            payload["dialogue"][name] = value
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, name):
                case_from_payload(payload)
        for name, value in (("turn_program", [123]), ("qa_split", ["dev"])):
            payload = json.loads(json.dumps(base))
            payload["dialogue"][name] = value
            with self.subTest(name=f"{name}-element"), self.assertRaisesRegex(ValueError, name):
                case_from_payload(payload)

    def test_execution_numeric_semantics_and_selection(self):
        self.assertTrue(score_numeric("0.18", "Final answer: 18%").exact_match)
        self.assertTrue(score_numeric("0.083", "Final answer: 8.3%").exact_match)
        self.assertFalse(score_numeric("100", "100 was intermediate; Final answer: 12").exact_match)
        self.assertTrue(score_numeric("5", "The year was 2020; the result was 5.").exact_match)
        self.assertTrue(score_numeric("-4", "decreased by $4 million").exact_match)
        self.assertTrue(score_numeric("2200", "$2.2 billion", "expressed in millions").exact_match)
        self.assertTrue(score_numeric("2.2", "2200 million", "also in billions").exact_match)
        self.assertTrue(score_numeric("1.23457", "Final answer: 1.234574").exact_match)
        # The intermediate 100 is closer to gold than the final 9, but must not win.
        self.assertFalse(score_numeric("101", "100 was used; final result is 9").exact_match)


class CohortTests(unittest.TestCase):
    def test_exact_cohort_builds_balanced_90_samples(self):
        self.assertEqual(set(TASK_CONFIG), {"dataset_ids", "targets", "split"})
        self.assertEqual(tuple(TASK_CONFIG["targets"]), TARGETS)
        self.assertEqual(TASK_CONFIG["split"], "dev")
        self.assertEqual(len(IDS), 30)
        self.assertEqual(len(set(IDS)), 30)
        config = EvaluationConfig(
            dataset_ids=IDS,
            targets=TARGETS,
            dataset_path=str(ROOT / "data" / "convfinqa_dataset.json"),
            split="dev",
        )
        cases = load_cases(config)
        task = build_task(cases, config)
        self.assertEqual(len(cases), 30)
        self.assertEqual(len(task.dataset), 90)
        self.assertEqual(
            [
                sum(sample.metadata["target"] == target for sample in task.dataset)
                for target in TARGETS
            ],
            [30, 30, 30],
        )
