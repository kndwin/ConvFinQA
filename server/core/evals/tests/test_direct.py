import unittest
from contextlib import asynccontextmanager
from unittest.mock import patch

from evals.benchmarks.convfinqa.cases_schema import ConversationCase, ExpectedTurn
from evals.config_schema import EvaluationConfig
from evals.direct import execute_direct
from evals.targets_schema import TargetSpec


class DirectExecutorWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_current_model_provider_without_a_model_call(self):
        provider = object()
        entered = False
        service_args = None

        @asynccontextmanager
        async def fake_model_provider():
            nonlocal entered
            entered = True
            yield provider

        class FakeService:
            def __init__(self, *args):
                nonlocal service_args
                service_args = args

            async def run(self, _params, _repository):
                yield {"type": "TEXT_MESSAGE_CONTENT", "delta": "answer"}

        case = ConversationCase(
            dataset_id="case-1",
            document="document",
            turns=(ExpectedTurn(question="question", answer="answer"),),
        )
        target = TargetSpec(
            id="baseline:v1",
            approach="baseline",
            context_version="document-conversation:v1",
            context_hash="hash",
        )

        # Patching the provider at its public module boundary makes this a
        # construction-only check: no OpenAI client or network request occurs.
        with (
            patch("src.platform.openai.model_provider", fake_model_provider),
            patch(
                "src.module.agent_execution.agent_execution_service.AgentExecutionService",
                FakeService,
            ),
        ):
            observations = await execute_direct(
                case, target, EvaluationConfig(targets=(target.id,))
            )

        self.assertTrue(entered)
        self.assertIsNotNone(service_args)
        self.assertIs(service_args[0], provider)
        self.assertEqual(type(service_args[1]).__name__, "OpenAICodeExecutionProvider")
        self.assertEqual(observations[0].actual, "answer")


if __name__ == "__main__":
    unittest.main()
