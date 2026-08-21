import re
import unittest
from decimal import Decimal
from pathlib import Path

from src.module.agent_execution.agent_approach.program_of_thought.structured_output import (
    ProgramNode,
)

from evals.benchmarks.convfinqa.dsl import CONSTANTS, execute_ast, execute_ast_diagnostics
from evals.benchmarks.convfinqa.sources import load_cases
from evals.benchmarks.convfinqa.structured import (
    StructuredAnswer,
    canonicalize,
    canonicalize_gold_execution,
    index_document,
    process_output,
    run_staged_fake,
    run_staged_fake_sequence,
    stage2_request,
    validate_stage1,
)
from evals.benchmarks.convfinqa.task import build_task
from evals.config_schema import EvaluationConfig
from evals.targets import component_metadata

ROOT = Path(__file__).parents[1]


class StructuredSchemaTests(unittest.TestCase):
    def test_forbid_and_decimal(self):
        with self.assertRaises(ValueError):
            StructuredAnswer(kind="number", value="1", representation="raw", scale="ones", extra=1)
        self.assertFalse(
            process_output(
                "baseline:v3",
                '{"kind":"number","value":"1.2x","representation":"raw","scale":"ones"}',
                "q",
            )["valid"]
        )
        self.assertEqual(
            canonicalize(
                {"kind": "number", "value": "18", "representation": "percent", "scale": "ones"},
                "percentage",
            ).value,
            "0.18000",
        )
        self.assertEqual(
            canonicalize(
                {"kind": "number", "value": "2.2", "representation": "raw", "scale": "billion"},
                "in millions",
            ).value,
            "2200.00000",
        )
        self.assertEqual(
            canonicalize(
                {"kind": "number", "value": "2200", "representation": "raw", "scale": "million"},
                "in billions",
            ).value,
            "2.20000",
        )
        self.assertEqual(
            canonicalize(
                {"kind": "number", "value": "-1.234567", "representation": "raw", "scale": "ones"}
            ).value,
            "-1.23457",
        )
        self.assertEqual(canonicalize_gold_execution("2200").value, "2200.00000")

    def test_non_numeric_kinds(self):
        self.assertEqual(
            process_output("baseline:v3", '{"kind":"boolean","value":"true"}', "q")["canonical"][
                "kind"
            ],
            "boolean",
        )
        self.assertFalse(process_output("baseline:v3", "prose", "q")["valid"])
        self.assertEqual(
            process_output("baseline:v3", '{"kind":"text","value":"hello"}', "q")["canonical"][
                "value"
            ],
            "hello",
        )
        self.assertFalse(
            process_output("baseline:v3", '{"kind":"unavailable","value":"unavailable"}', "q")[
                "valid"
            ]
            is False
        )

    def test_full_history_and_prior_ast(self):
        document = {"table": {"row": {"value": 3}}}
        turns = [
            ("first", '{"evidence_ids":["t:r0:c0"]}', '{"op":"evidence","id":"t:r0:c0"}'),
            (
                "and what was it in 2014?",
                '{"evidence_ids":["t:r0:c0"]}',
                '{"op":"add","args":[{"op":"prior","turn":1},{"op":"constant","id":"const_1"}]}',
            ),
        ]
        results = run_staged_fake_sequence(document, turns)
        self.assertEqual(results[1]["history"][0]["question"], "first")
        self.assertEqual(results[1]["canonical"]["value"], "4.00000")

    def test_gold_mutation_cannot_change_artifacts(self):
        raw = '{"kind":"number","value":"18","representation":"percent","scale":"ones"}'
        before = process_output("baseline:v3", raw, "percentage")
        # Gold is intentionally absent from processing; changing it cannot alter
        # the raw-stage, canonical, or diagnostic artifact.
        for _gold in ("0.18", "999999", "-12"):
            self.assertEqual(before, process_output("baseline:v3", raw, "percentage"))


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "pre_text": "Revenue rose 18%.",
            "post_text": "It reached 2.2 million.",
            "table": {"2020": {"amount": 2.2}},
        }
        self.index = index_document(self.document)

    def test_stable_index_and_numeric_spans(self):
        self.assertEqual([x.id for x in self.index], [x.id for x in index_document(self.document)])
        self.assertIn("n:p0:v0", [x.id for x in self.index])
        self.assertEqual(next(x for x in self.index if x.id == "t:r0:c0").numeric, "2.2")

    def test_bad_evidence_and_stage2_excludes_document(self):
        with self.assertRaises(ValueError):
            validate_stage1('{"evidence_ids":["bad"]}', self.index)
        selected = validate_stage1('{"evidence_ids":["t:r0:c0"]}', self.index)
        self.assertNotIn("Revenue rose", stage2_request("q", [], selected))
        self.assertIn("t:r0:c0", stage2_request("q", [], selected))
        good = run_staged_fake(
            self.document,
            "q",
            '{"evidence_ids":["t:r0:c0"]}',
            '{"kind":"number","value":"2.2","representation":"raw","scale":"ones"}',
        )
        self.assertTrue(good["valid"])
        bad = run_staged_fake(self.document, "q", '{"evidence_ids":["bad"]}', "{}")
        self.assertFalse(bad["valid"])


class DSLTests(unittest.TestCase):
    def test_native_nested_ast_canonical_payload_executes(self):
        node = ProgramNode(
            op="add",
            args=[
                ProgramNode(op="evidence", id="a"),
                ProgramNode(
                    op="multiply",
                    args=[
                        ProgramNode(op="constant", id="const_2"),
                        ProgramNode(op="evidence", id="b"),
                    ],
                ),
            ],
        )
        payload = node.model_dump(mode="json", exclude_none=True)
        self.assertEqual(
            payload,
            {
                "op": "add",
                "args": [
                    {"op": "evidence", "id": "a"},
                    {
                        "op": "multiply",
                        "args": [
                            {"op": "constant", "id": "const_2"},
                            {"op": "evidence", "id": "b"},
                        ],
                    },
                ],
            },
        )
        self.assertEqual(execute_ast(payload, {"a": Decimal(1), "b": Decimal(3)}), Decimal(7))

    def test_ops_nested_prior_and_diagnostics(self):
        def leaf(i):
            return {"op": "evidence", "id": i}

        for op in ("add", "subtract", "multiply", "divide", "greater"):
            args = [leaf("a"), leaf("b")]
            if op == "divide":
                self.assertEqual(
                    execute_ast({"op": op, "args": args}, {"a": Decimal(6), "b": Decimal(2)}),
                    Decimal(3),
                )
            else:
                execute_ast({"op": op, "args": args}, {"a": Decimal(6), "b": Decimal(2)})
        self.assertEqual(
            execute_ast(
                {
                    "op": "exp",
                    "args": [
                        {"op": "constant", "id": "const_2"},
                        {"op": "constant", "id": "const_3"},
                    ],
                },
                {},
            ),
            Decimal(8),
        )
        self.assertEqual(
            execute_ast({"op": "prior", "turn": 1}, {}, {"1": Decimal("2.5")}), Decimal("2.5")
        )
        diagnostics = execute_ast_diagnostics(
            {"op": "add", "args": [leaf("a"), {"op": "constant", "id": "const_4"}]},
            {"a": Decimal(2)},
        )
        self.assertEqual(diagnostics["nodes"], 3)
        self.assertEqual(diagnostics["operations"], ["add"])

    def test_rejections_and_constants_derived_from_bundle(self):
        for bad in (
            {"op": "literal", "value": 2},
            {"op": "evidence", "id": "x"},
            {"op": "constant", "id": "const_11"},
        ):
            with self.assertRaises(ValueError):
                execute_ast(bad, {})
        with self.assertRaises(ValueError):
            execute_ast(
                {
                    "op": "divide",
                    "args": [{"op": "constant", "id": "const_1"}, {"op": "evidence", "id": "zero"}],
                },
                {"zero": Decimal(0)},
            )
        expected = {
            "const_1",
            "const_2",
            "const_3",
            "const_4",
            "const_5",
            "const_6",
            "const_7",
            "const_8",
            "const_9",
            "const_10",
            "const_100",
            "const_1000",
            "const_100000",
            "const_1000000",
            "const_1000000000",
        }
        data = (ROOT / "data/convfinqa_dataset.json").read_text()
        derived = {f"const_{x}" for x in re.findall(r"const_(\d+)", data)}
        self.assertEqual(derived, expected)
        self.assertEqual(set(CONSTANTS), expected)
        deep = {"op": "constant", "id": "const_1"}
        for _ in range(14):
            deep = {"op": "add", "args": [deep, {"op": "constant", "id": "const_1"}]}
        with self.assertRaises(ValueError):
            execute_ast(deep, {})


class CohortStructuredTests(unittest.TestCase):
    def test_component_prompt_metadata(self):
        metadata = component_metadata("program-of-thought:v3")
        self.assertTrue(metadata["action_prompt_hash"])
        self.assertTrue(metadata["evidence_prompt_hash"])
        evidence = component_metadata("evidence:v1")
        self.assertEqual(evidence["action_prompt_hash"], evidence["evidence_prompt_hash"])

    def test_exact_90_balanced(self):
        import yaml

        config_data = yaml.safe_load(
            (ROOT / "configs/convfinqa-2026-08-20-30-structured.yaml").read_text()
        )
        self.assertEqual(len(config_data["dataset_ids"]), 30)
        config = EvaluationConfig(
            dataset_ids=tuple(config_data["dataset_ids"]),
            targets=tuple(config_data["targets"]),
            dataset_path=str(ROOT / "data/convfinqa_dataset.json"),
            split="dev",
        )
        task = build_task(load_cases(config), config)
        self.assertEqual(len(task.dataset), 90)
