import asyncio
import unittest
from typing import cast

from ag_ui.core import (
    AssistantMessage,
    TextMessageContentEvent,
    UserMessage,
)
from agents.models.interface import ModelProvider

from src.module.agent_execution.agent_approach.baseline.prompts.registry import (
    V1 as BASELINE_PROMPT,
)
from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.agent_execution.agent_execution_repository import (
    InMemoryAgentExecutionRepository,
)
from src.module.agent_execution.agent_execution_runner import AgentExecutionRunner
from src.module.agent_execution.agent_execution_service_schema import AgentExecutionServiceRunParams
from src.module.agent_execution.test_support import _FAKE_PROVIDER, request


class AgentExecutionRunnerTests(unittest.TestCase):
    class FakeApproach:
        def __init__(self, model_provider: ModelProvider | None = _FAKE_PROVIDER, answers=()):
            self.model_provider = model_provider
            self.answers = iter(answers)
            self.inputs = []

        @property
        def is_configured(self):
            return self.model_provider is not None

        def stream(self, input_data):
            self.inputs.append(input_data)
            answer = next(self.answers, "")

            async def events():
                if answer:
                    yield TextMessageContentEvent(
                        message_id=input_data.assistant_message_id, delta=answer
                    )

            return events()

        def resolve_prompt(self, prompt_id="baseline:v1"):
            return BASELINE_PROMPT

        def render_context(self, version, document, transcript, question):
            from src.module.agent_execution.agent_approach.baseline.context.registry import resolve

            return resolve(version, document, transcript, question)

    def test_approach_selects_both_approachs_and_rejects_runtime_value(self):
        direct = self.FakeApproach()
        calculator = self.FakeApproach()
        runner = AgentExecutionRunner(direct, calculator)
        self.assertIs(runner.resolve_approach(AgentApproach.BASELINE), direct)
        self.assertIs(runner.resolve_approach(AgentApproach.BASELINE_TOOL), calculator)
        with self.assertRaises(ValueError):
            runner.resolve_approach(cast(AgentApproach, "invalid"))

    def test_two_turn_transcript_contains_actual_previous_answer(self):
        approach = self.FakeApproach(answers=("actual A1", "actual A2"))
        runner = AgentExecutionRunner(approach, approach)
        repository = InMemoryAgentExecutionRepository()

        async def exercise():
            await self._collect(
                runner.run(
                    AgentExecutionServiceRunParams(
                        approach=AgentApproach.BASELINE,
                        prompt_version=None,
                        context_version="document-conversation:v1",
                        model=OpenAIModel.GPT_5_MINI,
                        document="doc",
                        input_data=request([UserMessage(id="q1", content="Q1")]),
                        trace_metadata={},
                    ),
                    repository,
                )
            )
            await self._collect(
                runner.run(
                    AgentExecutionServiceRunParams(
                        approach=AgentApproach.BASELINE,
                        prompt_version=None,
                        context_version="document-conversation:v1",
                        model=OpenAIModel.GPT_5_MINI,
                        document="doc",
                        input_data=request(
                            [
                                UserMessage(id="q1", content="Q1"),
                                AssistantMessage(id="a1", content="golden sentinel"),
                                UserMessage(id="q2", content="Q2"),
                            ]
                        ),
                        trace_metadata={},
                    ),
                    repository,
                )
            )

        asyncio.run(exercise())
        self.assertEqual(
            [(message.role, message.content) for message in asyncio.run(repository.messages())],
            [
                ("user", "Q1"),
                ("assistant", "actual A1"),
                ("user", "Q2"),
                ("assistant", "actual A2"),
            ],
        )
        self.assertEqual(approach.inputs[0].question, "Q1")
        self.assertEqual(
            [(item.role, item.content) for item in approach.inputs[1].transcript],
            [("user", "Q1"), ("assistant", "actual A1")],
        )
        self.assertEqual(approach.inputs[1].transcript[1].content, "actual A1")
        self.assertNotIn("golden sentinel", str(approach.inputs[1].transcript))

    def test_configuration_error_persists_nothing(self):
        repository = InMemoryAgentExecutionRepository()
        runner = AgentExecutionRunner(
            self.FakeApproach(model_provider=None), self.FakeApproach(model_provider=None)
        )

        async def exercise():
            return await self._collect(
                runner.run(
                    AgentExecutionServiceRunParams(
                        approach=AgentApproach.BASELINE,
                        prompt_version=None,
                        context_version="document-conversation:v1",
                        model=OpenAIModel.GPT_5_MINI,
                        document="doc",
                        input_data=request(),
                        trace_metadata={},
                    ),
                    repository,
                )
            )

        events = asyncio.run(exercise())
        self.assertEqual(events[-1].code, "configuration_error")
        self.assertEqual(asyncio.run(repository.messages()), ())

    def test_empty_approach_leaves_user_without_assistant(self):
        repository = InMemoryAgentExecutionRepository()
        approach = self.FakeApproach(answers=("",))
        runner = AgentExecutionRunner(approach, approach)

        async def exercise():
            return await self._collect(
                runner.run(
                    AgentExecutionServiceRunParams(
                        approach=AgentApproach.BASELINE,
                        prompt_version=None,
                        context_version="document-conversation:v1",
                        model=OpenAIModel.GPT_5_MINI,
                        document="doc",
                        input_data=request(),
                        trace_metadata={},
                    ),
                    repository,
                )
            )

        events = asyncio.run(exercise())
        self.assertEqual(events[-1].code, "run_error")
        self.assertEqual(
            [(message.role, message.content) for message in asyncio.run(repository.messages())],
            [("user", "question")],
        )

    async def _collect(self, iterator):
        return [event async for event in iterator]
