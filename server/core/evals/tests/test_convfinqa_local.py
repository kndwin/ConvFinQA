import json
import os
import tempfile
import unittest
from pathlib import Path

from evals.benchmarks.convfinqa.sources import load_cases
from evals.benchmarks.convfinqa.task import DEFAULT_DATASET_PATH, convfinqa
from evals.config_schema import EvaluationConfig


def config(path: Path, **kwargs):
    return EvaluationConfig(targets=("target",), dataset_path=str(path), **kwargs)


class LocalConvFinQATests(unittest.TestCase):
    def test_task_uses_bundled_dataset_outside_current_working_directory(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                task = convfinqa(
                    dataset_ids="Single_MRO/2007/page_134.pdf-1", targets="baseline:v1"
                )
            finally:
                os.chdir(original_cwd)

        self.assertEqual(
            task.dataset.samples[0].metadata["case"]["dataset_id"],
            "Single_MRO/2007/page_134.pdf-1",
        )
        self.assertTrue(DEFAULT_DATASET_PATH.is_absolute())
        self.assertEqual(DEFAULT_DATASET_PATH.name, "convfinqa_dataset.json")

    def test_integer_dataset_ids_are_normalized(self):
        self.assertEqual(
            EvaluationConfig(targets=("target",), dataset_ids=(4,)).dataset_ids, ("4",)
        )

    def fixture(self):
        return {
            "train": [
                {
                    "id": "a/b-1_x.y",
                    "doc": {"pre_text": "doc"},
                    "dialogue": {
                        "conv_questions": ["q1", "q2"],
                        "conv_answers": ["a1", "extra", "ignored"],
                    },
                }
            ],
            "dev": [
                {
                    "id": "dev-id",
                    "doc": {},
                    "dialogue": {
                        "conv_questions": ["dev question"],
                        "conv_answers": ["dev answer"],
                    },
                }
            ],
        }

    def write(self, value):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump(value, handle)
            path = Path(handle.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_dev_default_and_train_string_id(self):
        path = self.write(self.fixture())
        self.assertEqual(load_cases(config(path))[0].dataset_id, "dev-id")
        cases = load_cases(config(path, split="train", dataset_ids=("a/b-1_x.y",)))
        self.assertEqual(cases[0].dataset_id, "a/b-1_x.y")
        self.assertEqual([turn.answer for turn in cases[0].turns], ["a1", "extra"])

    def test_filter_not_found_and_duplicate(self):
        path = self.write(self.fixture())
        with self.assertRaisesRegex(ValueError, "not found"):
            load_cases(config(path, dataset_ids=("missing",)))
        data = self.fixture()
        data["dev"].append(data["dev"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_cases(config(self.write(data)))

    def test_malformed_and_missing_answer(self):
        data = self.fixture()
        data["dev"][0]["dialogue"]["conv_answers"] = []
        path = self.write(data)
        self.assertIsNone(load_cases(config(path))[0].turns[0].answer)
        data["dev"][0]["dialogue"] = "bad"
        with self.assertRaises(ValueError):
            load_cases(config(self.write(data)))

    def test_local_source_id_and_required_payload_fields(self):
        path = self.write(self.fixture())
        case = load_cases(config(path))[0]
        self.assertEqual(case.source_id, "dev-id")
        for field in ("doc", "dialogue"):
            data = self.fixture()
            del data["dev"][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                load_cases(config(self.write(data)))
        data = self.fixture()
        data["dev"][0]["doc"] = []
        with self.assertRaises(ValueError):
            load_cases(config(self.write(data)))


if __name__ == "__main__":
    unittest.main()
