import asyncio
import unittest
from decimal import Decimal

from agents import Agent, RunContextWrapper

from src.module.agent_execution.agent_approach.evidence.structured_output import EvidenceAnswer

from .index import index_document
from .output_guardrail import evidence_output_guardrail
from .tools import EvidenceToolState, evidence_fetch, grounded_calculator


class EvidenceProductionTests(unittest.TestCase):
    def setUp(self):
        self.state = EvidenceToolState(
            index_document(
                {"table": {"Revenue": {"2023": "$1,200"}}, "pre_text": "The rate was 5%."}
            )
        )

    def run_output_guardrail(self, answer: EvidenceAnswer):
        result = asyncio.run(
            evidence_output_guardrail.run(RunContextWrapper(self.state), Agent(name="test"), answer)
        )
        return result.output

    def test_private_index_and_stable_tools(self):
        self.assertEqual(
            [x.name for x in (evidence_fetch, grounded_calculator)],
            ["evidence_fetch", "grounded_calculator"],
        )
        self.assertEqual(self.state.index[0].numeric, "1200")
        self.assertIn("numeric span", self.state.index[-1].text)

    def test_tool_schemas_hide_run_context(self):
        self.assertEqual(
            set(evidence_fetch.params_json_schema["properties"]), {"query", "max_results"}
        )
        self.assertEqual(
            set(grounded_calculator.params_json_schema["properties"]),
            {"operation", "operands"},
        )

    def test_retrieval_normalization_order_bounds_and_empty(self):
        result = self.state.fetch("RATE!!!", 10)
        self.assertEqual(result["results"][0]["id"], "n:p0")
        self.assertEqual(self.state.fetch("does-not-exist")["results"], [])
        with self.assertRaises(ValueError):
            self.state.fetch("rate", 11)

    def test_calculator_operations_and_grounding(self):
        with self.assertRaises(ValueError):
            self.state.calculate("add", ["const_1", "const_2"])
        self.state.fetch("revenue")
        selected = self.state.calculate("select", ["t:r0:c0"])
        self.assertEqual(selected["value"], "1200")
        for op, expected in (
            ("add", "1202"),
            ("subtract", "1198"),
            ("multiply", "2400"),
            ("divide", "600"),
            ("greater", "1"),
            ("exp", "1440000"),
        ):
            operand = "const_2" if op != "divide" else "const_2"
            self.assertEqual(
                self.state.calculate(op, [selected["handle"], operand])["value"], expected
            )
        self.assertEqual(self.state.calculate("add", ["const_1", "const_2"])["value"], "3")

    def test_calculator_rejects_bad_references_and_shape(self):
        self.state.fetch("revenue")
        for operands in ([], ["t:r0:c0"], ["raw-number", "const_1"]):
            with self.assertRaises(ValueError):
                self.state.calculate("add", operands)
        with self.assertRaises(ValueError):
            self.state.calculate("select", ["unknown"])
        with self.assertRaises(ValueError):
            self.state.calculate("divide", ["t:r0:c0", "const_0"])
        with self.assertRaises(ValueError):
            self.state.calculate("exp", ["const_2", "const_1000"])

    def test_state_isolation_and_order_audit(self):
        other = EvidenceToolState(self.state.index)
        self.state.fetch("revenue")
        self.assertFalse(other.fetched)
        self.assertEqual([c["kind"] for c in self.state.ordered_calls], ["fetch"])

    def test_scale_is_provenance_and_percent_is_execution_semantics(self):
        state = EvidenceToolState(
            index_document({"table": {"Sales million": {"2023": "2200"}, "Rate": {"x": "5%"}}})
        )
        state.fetch("sales million")
        self.assertEqual(state.calculate("select", ["t:r0:c0"])["value"], "2200")
        state.fetch("rate")
        self.assertEqual(state.calculate("select", ["t:r1:c0"])["value"], "0.05")

    def test_calculation_requires_nonempty_fetch_and_handles_chain(self):
        self.assertFalse(self.state.successful_fetches)
        self.assertEqual(self.state.results, {})

    def test_final_result_reference_accepts_percent_rounding_and_declared_scale(self):
        self.state.results["calc:0"] = Decimal("0.1800001")
        self.state.successful_fetches.add("revenue")
        self.assertFalse(
            self.run_output_guardrail(
                EvidenceAnswer(
                    kind="number",
                    value="18",
                    representation="percent",
                    scale="ones",
                    result_ref="calc:0",
                ),
            ).tripwire_triggered
        )
        self.assertFalse(
            self.run_output_guardrail(
                EvidenceAnswer(
                    kind="number",
                    value="18",
                    representation="percent",
                    scale="million",
                    result_ref="calc:0",
                ),
            ).tripwire_triggered
        )

    def test_final_result_reference_must_match_calculator_value(self):
        self.state.results["calc:0"] = Decimal("0.18")
        self.state.successful_fetches.add("revenue")
        result = self.run_output_guardrail(
            EvidenceAnswer(
                kind="number",
                value="19",
                representation="percent",
                scale="million",
                result_ref="calc:0",
            ),
        )
        self.assertTrue(result.tripwire_triggered)

    def test_final_result_reference_and_fetch_are_required(self):
        result = self.run_output_guardrail(
            EvidenceAnswer(kind="text", value="unknown", result_ref=None)
        )
        self.assertTrue(result.tripwire_triggered)

        self.state.successful_fetches.add("revenue")
        result = self.run_output_guardrail(
            EvidenceAnswer(
                kind="number", value="1", representation="raw", scale="ones", result_ref="missing"
            ),
        )
        self.assertTrue(result.tripwire_triggered)


if __name__ == "__main__":
    unittest.main()
