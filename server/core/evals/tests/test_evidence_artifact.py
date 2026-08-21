import unittest
from decimal import Decimal
from types import SimpleNamespace

from src.module.agent_execution.agent_approach.evidence.run import _serialize_tool_result

from evals.benchmarks.convfinqa.structured import audit_evidence_tools, process_evidence_output
from evals.events import EventCollector


def collector(*calls):
    return SimpleNamespace(tools=list(calls), error=None)


def call(name, arguments, result):
    return SimpleNamespace(name=name, arguments=arguments, result=result)


class EvidenceArtifactTests(unittest.TestCase):
    def test_collected_tool_result_is_canonical_json_for_audit(self):
        events = EventCollector()
        events.add(
            {"type": "TOOL_CALL_START", "tool_call_id": "c1", "tool_call_name": "evidence_fetch"}
        )
        events.add({"type": "TOOL_CALL_ARGS", "tool_call_id": "c1", "delta": '{"query":"x"}'})
        events.add(
            {
                "type": "TOOL_CALL_RESULT",
                "tool_call_id": "c1",
                "content": _serialize_tool_result(
                    {"results": [{"id": "t1", "provenance": Decimal("1")}]}
                ),
            }
        )
        self.assertEqual(events.tools[0].result, '{"results":[{"id":"t1","provenance":"1"}]}')
        audited = audit_evidence_tools(events.tools)
        self.assertFalse(audited["errors"])

    def test_audit_rejects_non_object_payloads(self):
        audited = audit_evidence_tools(
            [call("evidence_fetch", "[]", '{"results": []}'), call("evidence_fetch", "{}", "[]")]
        )
        self.assertFalse(audited["ordering_valid"])
        self.assertEqual(len(audited["errors"]), 2)
        self.assertTrue(all("JSON object" in error for error in audited["errors"]))

    def test_valid_native_artifact_rounds_authoritative_result(self):
        c = collector(
            call(
                "evidence_fetch",
                '{"query":"x"}',
                '{"results":[{"id":"t1","provenance":"table[x]"}]}',
            ),
            call(
                "grounded_calculator",
                '{"operands":["t1"]}',
                '{"handle":"calc:0","value":"1.234567"}',
            ),
        )
        artifact = process_evidence_output(
            "evidence:v1",
            '{"kind":"number","value":"1.23457","representation":"raw","scale":"ones","result_ref":"calc:0"}',
            "q",
            c,
        )
        self.assertTrue(artifact["valid"])
        self.assertEqual(artifact["canonical"]["value"], "1.23457")

    def test_failed_literal_calculator_then_grounded_retry_is_valid_and_audited(self):
        artifact = process_evidence_output(
            "evidence:v1",
            '{"kind":"number","value":"1","representation":"raw","scale":"ones",'
            '"result_ref":"calc:0"}',
            "q",
            collector(
                call(
                    "evidence_fetch", '{"query":"x"}', '{"results":[{"id":"t1","provenance":"p"}]}'
                ),
                call("grounded_calculator", '{"operands":["1"]}', '"raw numeric operands"'),
                call(
                    "grounded_calculator", '{"operands":["t1"]}', '{"handle":"calc:0","value":"1"}'
                ),
            ),
        )
        self.assertTrue(artifact["valid"])
        self.assertEqual(len(artifact["failed_tool_calls"]), 1)
        self.assertEqual(artifact["failed_tool_calls"][0]["tool"], "grounded_calculator")

    def test_failed_fetch_then_valid_fetch_is_valid(self):
        audited = audit_evidence_tools(
            [
                call(
                    "evidence_fetch",
                    '{"query":"x","max_results":11}',
                    '"max_results must be between 1 and 10"',
                ),
                call(
                    "evidence_fetch",
                    '{"query":"x","max_results":1}',
                    '{"results":[{"id":"t1","provenance":"p"}]}',
                ),
            ]
        )
        self.assertTrue(audited["ordering_valid"])
        self.assertEqual(len(audited["fetched_evidence"]), 1)
        self.assertEqual(len(audited["failed_tool_calls"]), 1)

    def test_failed_calls_without_successful_recovery_remain_invalid(self):
        artifact = process_evidence_output(
            "evidence:v1",
            '{"kind":"number","value":"1","result_ref":"calc:0"}',
            "q",
            collector(call("evidence_fetch", '{"query":"x"}', '"no matches"')),
        )
        self.assertFalse(artifact["valid"])
        self.assertIn("no successful evidence fetch", artifact["validation_error"])

    def test_invalid_order_and_result_ref_are_scored_invalid(self):
        c = collector(
            call("grounded_calculator", '{"operands":["t1"]}', '{"handle":"calc:0","value":"1"}'),
            call("evidence_fetch", '{"query":"x"}', '{"results":[{"id":"t1","provenance":"p"}]}'),
        )
        invalid = process_evidence_output(
            "evidence:v1",
            '{"kind":"number","value":"1","representation":"raw","scale":"ones","result_ref":"calc:9"}',
            "q",
            c,
        )
        self.assertFalse(invalid["valid"])
        self.assertIn("calculator before", invalid["validation_error"])
        valid_order_bad_ref = process_evidence_output(
            "evidence:v1",
            '{"kind":"number","value":"1","representation":"raw",'
            '"scale":"million","result_ref":"calc:9"}',
            "q",
            collector(
                call(
                    "evidence_fetch",
                    '{"query":"x"}',
                    '{"results":[{"id":"t1","provenance":"p"}]}',
                ),
                call(
                    "grounded_calculator",
                    '{"operands":["t1"]}',
                    '{"handle":"calc:0","value":"1"}',
                ),
            ),
        )
        self.assertFalse(valid_order_bad_ref["valid"])
        self.assertIn("result_ref", valid_order_bad_ref["validation_error"])

    def test_empty_or_prose_output_never_regex_falls_back(self):
        empty = process_evidence_output("evidence:v1", "The answer is 42", "q", collector())
        self.assertFalse(empty["valid"])
        self.assertNotIn("canonical", empty)


if __name__ == "__main__":
    unittest.main()
