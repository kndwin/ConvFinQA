import unittest
from unittest.mock import patch

from src.module.agent_execution.agent_approach.baseline.prompts.registry import (
    V1,
    V2,
    V3,
)
from src.module.agent_execution.agent_approach.baseline.run import BaselineApproach
from src.module.agent_execution.agent_approach.baseline.structured_output import (
    StructuredAnswer,
)
from src.module.agent_execution.agent_execution_runner_schema import ApproachInput


class BaselineOutputSchemaTests(unittest.TestCase):
    def test_schema_mapping_and_legacy_plain_text(self):
        approach = BaselineApproach(None)
        for prompt, expected in (
            (V1, None),
            (V2, None),
            (V3, StructuredAnswer),
        ):
            data = ApproachInput(
                prompt=prompt,
                context=approach.render_context("document-conversation:v1", "D", (), "Q"),
                model="model",
                trace_metadata={},
                assistant_message_id="a",
                transcript=(),
                question="Q",
            )
            with patch(
                "src.module.agent_execution.agent_approach.baseline.run.build_agent"
            ) as build:
                build.return_value = object()
                approach._stream = lambda *args: object()  # type: ignore[method-assign]
                approach._events = lambda *args: iter(())  # type: ignore[method-assign]
                approach._events_structured = lambda *args: iter(())  # type: ignore[method-assign]
                approach.stream(data)
                self.assertIs(build.call_args.kwargs.get("output_type"), expected)
