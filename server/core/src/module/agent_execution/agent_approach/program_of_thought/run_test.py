import asyncio
import hashlib
import unittest
from types import SimpleNamespace
from typing import cast, get_type_hints
from unittest.mock import patch

from ag_ui.core import (
    RunAgentInput,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    UserMessage,
)
from agents import RunResultStreaming

from src.module.agent_execution.agent_approach.program_of_thought.context.registry import (
    resolve as context,
)
from src.module.agent_execution.agent_approach.program_of_thought.prompts.registry import V1, V2, V3
from src.module.agent_execution.agent_approach.program_of_thought.run import (
    ProgramOfThoughtApproach,
)
from src.module.agent_execution.agent_approach.program_of_thought.structured_output import (
    ProgramNode,
)
from src.module.agent_execution.agent_approach.shared.base_agent_approach import BaseAgentApproach
from src.module.agent_execution.agent_approach.shared.tools.code_execution.provider import (
    CodeExecutionProvider,
)
from src.module.agent_execution.agent_execution_constants import (
    DEFAULT_PROMPT_VERSIONS,
    AgentApproach,
    OpenAIModel,
)
from src.module.agent_execution.agent_execution_repository import InMemoryAgentExecutionRepository
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import ApproachInput
from src.module.agent_execution.agent_execution_service import AgentExecutionService
from src.module.agent_execution.agent_execution_service_schema import AgentExecutionServiceRunParams
from src.platform.openai.code_execution_provider import (
    OpenAICodeExecutionProvider,
)


def request(messages=None) -> RunAgentInput:
    return RunAgentInput(
        thread_id="thread",
        run_id="run",
        state={},
        messages=(
            [UserMessage(id="client-message", content="question")] if messages is None else messages
        ),
        tools=[],
        context=[],
        forwarded_props={},
    )


class ProgramOfThoughtTests(unittest.TestCase):
    def test_tool_policy_preserves_v1_v2_and_disables_v3(self):
        approach = ProgramOfThoughtApproach(None, OpenAICodeExecutionProvider())
        context_value = context("document-conversation:v1", "DOC", (), "Q")
        for prompt, required in ((V1, True), (V2, True), (V3, False)):
            data = ApproachInput(
                prompt=prompt,
                context=context_value,
                model="model",
                trace_metadata={},
                assistant_message_id="assistant",
                transcript=(),
                question="Q",
            )
            with patch(
                "src.module.agent_execution.agent_approach.program_of_thought.run.build_agent"
            ) as build:
                build.return_value = object()
                with (
                    patch.object(approach, "_stream", return_value=object()),
                    patch.object(approach, "_events_with_code", return_value=iter(())),
                    patch.object(approach, "_events", return_value=iter(())),
                ):
                    approach.stream(data)
                kwargs = build.call_args.kwargs
                self.assertEqual(bool(kwargs.get("require_tool", False)), required)
                self.assertEqual(kwargs.get("tools", []) != [], required)

    def test_structured_event_serializes_one_payload(self):
        class Stream:
            final_output = ProgramNode(
                op="add",
                args=[
                    ProgramNode(op="constant", id="const_2"),
                    ProgramNode(op="evidence", id="e"),
                ],
            )
            context_wrapper = SimpleNamespace(usage=None)

            async def stream_events(self):
                if False:
                    yield None

        data = ApproachInput(
            prompt=V3,
            context=context("document-conversation:v1", "D", (), "Q"),
            model="model",
            trace_metadata={},
            assistant_message_id="a",
            transcript=(),
            question="Q",
        )
        events = asyncio.run(
            self._collect(
                ProgramOfThoughtApproach(None, OpenAICodeExecutionProvider())._events_structured(
                    data, Stream()
                )
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0].delta,
            '{"args":[{"id":"const_2","op":"constant"},{"id":"e","op":"evidence"}],"op":"add"}',
        )

    def test_registry_default_hash_and_context(self):
        self.assertEqual(AgentApproach.PROGRAM_OF_THOUGHT, V1.approach)
        self.assertEqual(DEFAULT_PROMPT_VERSIONS[AgentApproach.PROGRAM_OF_THOUGHT], V1.id)
        self.assertEqual(V1.content_hash, hashlib.sha256(V1.instructions.encode()).hexdigest())
        rendered = context(
            "document-conversation:v1",
            "DOC",
            (ConversationMessage(role="user", content="old"),),
            "Q",
        )
        self.assertIn("DOC", rendered.rendered)
        self.assertIn("Q", rendered.rendered)

    def test_provider_is_neutral_and_uses_current_openai_config(self):
        self.assertIn("Tool", str(get_type_hints(CodeExecutionProvider.tool)["return"]))
        self.assertEqual(
            OpenAICodeExecutionProvider().tool().tool_config,
            {"type": "code_interpreter", "container": {"type": "auto"}},
        )

    def test_missing_client_for_program_of_thought_is_configuration_error(self):
        params = AgentExecutionServiceRunParams(
            approach=AgentApproach.PROGRAM_OF_THOUGHT,
            prompt_version=None,
            context_version="document-conversation:v1",
            model=OpenAIModel.GPT_5_MINI,
            document="DOC",
            input_data=request(),
            trace_metadata={},
        )
        events = asyncio.run(
            self._collect(
                AgentExecutionService(None, OpenAICodeExecutionProvider()).run(
                    params, InMemoryAgentExecutionRepository()
                )
            )
        )
        self.assertEqual(events[-1].code, "configuration_error")

    def test_hosted_code_events_have_one_lifecycle_and_result(self):
        class Stream:
            final_output = "final"

            async def stream_events(self):
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(
                        type="response.code_interpreter_call_code.delta",
                        item_id="call",
                        delta="print(1)",
                    ),
                )
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(
                        type="response.code_interpreter_call.completed", item_id="call"
                    ),
                )
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(
                        type="response.output_item.done",
                        item=SimpleNamespace(
                            id="call",
                            type="code_interpreter_call",
                            status="completed",
                            container_id="container",
                            code="print(1)",
                            outputs=[{"type": "logs", "logs": "1"}],
                        ),
                    ),
                )
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(type="response.output_text.delta", delta="final"),
                )

            def cancel(self):
                self.cancelled = True

        approach = ProgramOfThoughtApproach(None, OpenAICodeExecutionProvider())
        data = cast(ApproachInput, SimpleNamespace(assistant_message_id="message"))
        events = asyncio.run(
            self._collect(approach._events_with_code(data, cast(RunResultStreaming, Stream())))
        )
        self.assertEqual(sum(isinstance(event, ToolCallStartEvent) for event in events), 1)
        self.assertEqual(sum(isinstance(event, ToolCallArgsEvent) for event in events), 1)
        self.assertEqual(sum(isinstance(event, ToolCallEndEvent) for event in events), 1)
        self.assertEqual(sum(isinstance(event, ToolCallResultEvent) for event in events), 1)
        self.assertEqual(events[-1].delta, "final")

    def test_shared_usage_helper_preserves_each_request_and_sdk_total(self):
        stream = cast(
            RunResultStreaming,
            SimpleNamespace(
                context_wrapper=SimpleNamespace(
                    usage=SimpleNamespace(
                        input_tokens=7,
                        output_tokens=3,
                        total_tokens=12,
                        request_usage_entries=[
                            SimpleNamespace(
                                input_tokens=4,
                                output_tokens=2,
                                total_tokens=7,
                                input_tokens_details=SimpleNamespace(cached_tokens=1),
                                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
                            ),
                            SimpleNamespace(
                                input_tokens=3,
                                output_tokens=1,
                                total_tokens=5,
                                input_tokens_details=SimpleNamespace(cached_tokens=0),
                                output_tokens_details=SimpleNamespace(reasoning_tokens=2),
                            ),
                        ],
                    )
                )
            ),
        )
        data = cast(ApproachInput, SimpleNamespace(model="test-model"))
        event = BaseAgentApproach._model_usage_event(data, stream)
        assert event is not None
        self.assertEqual(event.value["calls"][0]["total_tokens"], 7)
        self.assertEqual(event.value["calls"][1]["total_tokens"], 5)

    def test_cancellation_cancels_hosted_stream(self):
        class Stream:
            final_output = None
            cancelled = False

            async def stream_events(self):
                await asyncio.sleep(10)
                yield SimpleNamespace()

            def cancel(self):
                self.cancelled = True

        stream = Stream()
        approach = ProgramOfThoughtApproach(None, OpenAICodeExecutionProvider())

        async def exercise():
            task = asyncio.create_task(
                self._collect(
                    approach._events_with_code(
                        cast(ApproachInput, SimpleNamespace(assistant_message_id="message")),
                        cast(RunResultStreaming, stream),
                    )
                )
            )
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(exercise())
        self.assertTrue(stream.cancelled)

    async def _collect(self, iterator):
        return [event async for event in iterator]
