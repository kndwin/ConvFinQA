import asyncio
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from ag_ui.core import AssistantMessage, EventType, RunAgentInput, UserMessage
from agents import Agent
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import RunItemStreamEvent
from openai import AsyncOpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from src.module.chat_sessions.agent.calculator_mini_chat_agent import (
    CALCULATOR_INSTRUCTIONS,
    CalculatorMiniChatAgent,
    calculator,
)
from src.module.chat_sessions.agent.direct_mini_chat_agent import (
    INSTRUCTIONS,
    DirectMiniChatAgent,
    _history,
    newest_user_message,
    newest_user_text,
)
from src.module.chat_sessions.chat_sessions_constants import AgentVariant
from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
from src.module.chat_sessions.chat_sessions_router_schema import (
    ChatSessionCreateRequest,
    ChatSessionResponse,
)
from src.module.chat_sessions.chat_sessions_service import ChatSessionService
from src.module.chat_sessions.chat_sessions_service_schema import (
    ChatSessionServiceCreateParams,
    ChatSessionServiceDeleteParams,
    ChatSessionServiceGetParams,
    ChatSessionServiceListParams,
    ChatSessionServiceUpdateParams,
)
from src.module.dataset_conversations.dataset_conversations_repository import (
    DatasetConversationRepository,
)
from src.platform.database.models import (
    ChatMessageTable,
    ChatSessionTable,
    DatasetConversationTable,
)
from src.platform.observability import NOOP_OBSERVABILITY, Observability


class ChatSessionVariantSchemaTests(unittest.TestCase):
    def test_create_request_defaults_to_direct_mini(self) -> None:
        self.assertEqual(ChatSessionCreateRequest().agent_variant, AgentVariant.DIRECT_MINI)

    def test_create_request_accepts_explicit_direct_mini(self) -> None:
        self.assertEqual(
            ChatSessionCreateRequest(agent_variant="direct-mini").agent_variant,
            AgentVariant.DIRECT_MINI,
        )

    def test_create_request_rejects_unknown_variant(self) -> None:
        with self.assertRaises(ValidationError):
            ChatSessionCreateRequest(agent_variant="unknown")

    def test_openapi_describes_optional_variant_and_rejects_unknown_http_value(self) -> None:
        from fastapi.testclient import TestClient
        from src.main import create_app

        app = create_app()
        schema = app.openapi()
        request_schema = schema["components"]["schemas"]["ChatSessionCreateRequest"]
        self.assertFalse(request_schema.get("required"))
        self.assertEqual(
            request_schema["properties"]["agent_variant"]["$ref"],
            "#/components/schemas/AgentVariant",
        )
        self.assertEqual(
            schema["components"]["schemas"]["AgentVariant"]["enum"],
            ["direct-mini", "calculator-mini"],
        )
        response = TestClient(app).post(
            "/dataset-conversations/1/chat-sessions", json={"agent_variant": "unknown"}
        )
        self.assertEqual(response.status_code, 422)

    def test_create_request_accepts_calculator_mini(self) -> None:
        self.assertEqual(
            ChatSessionCreateRequest(agent_variant="calculator-mini").agent_variant,
            AgentVariant.CALCULATOR_MINI,
        )

    def test_response_exposes_persisted_variant(self) -> None:
        from datetime import UTC, datetime

        response = ChatSessionResponse.model_validate(
            ChatSessionTable(
                id=8,
                dataset_conversation_id=3,
                agent_variant="direct-mini",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        self.assertEqual(response.agent_variant, AgentVariant.DIRECT_MINI)


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


class ChatInputTests(unittest.TestCase):
    def test_actual_tanstack_shape_uses_newest_nonblank_user_and_its_id(self) -> None:
        input_data = request(
            [
                UserMessage(id="old", content="old question"),
                UserMessage(id="blank", content="  "),
                UserMessage(
                    id="new",
                    content=[
                        {"type": "text", "text": " new"},
                        {"type": "text", "text": " question "},
                    ],
                ),
            ]
        )
        self.assertEqual(newest_user_message(input_data), ("new question", "new"))
        self.assertEqual(newest_user_text(input_data), "new question")

    def test_missing_user_message(self) -> None:
        self.assertIsNone(newest_user_message(request([])))

    def test_history_uses_messages_before_newest_identical_question(self) -> None:
        question = "repeat me"
        input_data = request(
            [
                UserMessage(id="old", content=question),
                AssistantMessage(id="answer", content="an answer"),
                UserMessage(id="new", content=question),
            ]
        )
        self.assertEqual(_history(input_data, question), "user: repeat me\nassistant: an answer")


class ChatSessionServiceTests(unittest.TestCase):
    def test_crud_delegates_with_exact_ids(self):
        class SessionFake:
            def __init__(self):
                self.calls = []
                self.value = ChatSessionTable(id=8, dataset_conversation_id=3)

            async def list(self, params):
                self.calls.append(("list", params.dataset_conversation_id))
                return [self.value]

            async def get(self, params):
                self.calls.append(("get", params.dataset_conversation_id, params.chat_session_id))
                return self.value

            async def messages(self, params):
                self.calls.append(
                    ("messages", params.dataset_conversation_id, params.chat_session_id)
                )
                return []

            async def create(self, params):
                self.calls.append(("create", params.dataset_conversation_id, params.agent_variant))
                return self.value

            async def update(self, params):
                self.calls.append(
                    ("update", params.dataset_conversation_id, params.chat_session_id, params.title)
                )
                return self.value

            async def delete(self, params):
                self.calls.append(
                    ("delete", params.dataset_conversation_id, params.chat_session_id)
                )
                return True

        class DatasetFake:
            async def get(self, params):
                return SimpleNamespace(id=params.dataset_conversation_id)

        repository = SessionFake()
        service = ChatSessionService(
            cast(ChatSessionRepository, repository),
            cast(DatasetConversationRepository, DatasetFake()),
            cast(Observability, NOOP_OBSERVABILITY),
        )

        async def exercise():
            await service.list(ChatSessionServiceListParams(dataset_conversation_id=3))
            await service.get(
                ChatSessionServiceGetParams(dataset_conversation_id=3, chat_session_id=8)
            )
            await service.messages(
                ChatSessionServiceGetParams(dataset_conversation_id=3, chat_session_id=8)
            )
            await service.create(
                ChatSessionServiceCreateParams(
                    dataset_conversation_id=3, agent_variant=AgentVariant.DIRECT_MINI
                )
            )
            await service.update(
                ChatSessionServiceUpdateParams(
                    dataset_conversation_id=3, chat_session_id=8, title="Title"
                )
            )
            await service.delete(
                ChatSessionServiceDeleteParams(dataset_conversation_id=3, chat_session_id=8)
            )

        asyncio.run(exercise())
        self.assertEqual(
            repository.calls,
            [
                ("list", 3),
                ("get", 3, 8),
                ("messages", 3, 8),
                ("create", 3, AgentVariant.DIRECT_MINI),
                ("update", 3, 8, "Title"),
                ("delete", 3, 8),
            ],
        )


class ScalarResult:
    def __init__(self, scalar=None, rows=()):
        self.scalar = scalar
        self.rows = rows

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self.rows)


class FakeSession:
    def __init__(
        self,
        *,
        session=True,
        doc_json='{"source":"full document"}',
        rows=(),
        agent_variant="direct-mini",
    ):
        self.chat_session = (
            ChatSessionTable(id=7, dataset_conversation_id=3, agent_variant=agent_variant)
            if session
            else None
        )
        self.dataset = DatasetConversationTable(
            id=3, source_id="source", split="train", doc_json=doc_json
        )
        self.rows = rows
        self.execute_count = 0
        self.added = []
        self.sequence = []

    async def execute(self, statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return ScalarResult(self.chat_session)
        return ScalarResult(rows=self.rows)

    async def get(self, model, identifier):
        return self.dataset

    def add(self, value):
        self.added.append(value)
        self.sequence.append(f"add:{getattr(value, 'role', '?')}")

    async def commit(self):
        self.sequence.append("commit")

    async def rollback(self):
        self.sequence.append("rollback")


class FakeClient:
    instances = []

    def __init__(self, **kwargs):
        self.closed = False
        self.kwargs = kwargs
        self.__class__.instances.append(self)

    async def close(self):
        self.closed = True


class FakeStream:
    def __init__(
        self, deltas=("Hello", " world"), final_output="Hello world", error=None, events=None
    ):
        self.deltas = deltas
        self.final_output = final_output
        self.error = error
        self.events = events
        self.cancelled = False

    async def stream_events(self):
        if self.error:
            raise self.error
        if self.events is not None:
            for event in self.events:
                yield event
        else:
            for delta in self.deltas:
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(type="response.output_text.delta", delta=delta),
                )

    def cancel(self):
        self.cancelled = True


class MiniChatAgentTests(unittest.TestCase):
    def agent(self, session, client=None, agent_type=DirectMiniChatAgent):
        observability = cast(Observability, NOOP_OBSERVABILITY)
        async_session = cast(AsyncSession, session)
        return agent_type(
            chat_session_repository=ChatSessionRepository(async_session, observability),
            dataset_conversation_repository=DatasetConversationRepository(
                async_session, observability
            ),
            openai_client=cast(AsyncOpenAI | None, client),
            observability=observability,
        )

    def run_agent(self, session, stream, input_data=None, agent_type=DirectMiniChatAgent):
        captured = {}
        client = FakeClient()
        self.last_client = client

        def run_streamed(agent, model_input, **kwargs):
            captured.update(agent=agent, input=model_input, kwargs=kwargs)
            return stream

        async def collect():
            events = []
            async for event in self.agent(session, client, agent_type).run(
                3, 7, input_data or request()
            ):
                session.sequence.append(event.type.value)
                events.append(event)
            return events

        with (
            patch(
                "src.module.chat_sessions.agent.direct_mini_chat_agent.OpenAIProvider",
                lambda **_: object(),
            ),
            patch(
                "src.module.chat_sessions.agent.direct_mini_chat_agent.Runner.run_streamed",
                run_streamed,
            ),
            patch(
                "src.module.chat_sessions.agent.calculator_mini_chat_agent.OpenAIProvider",
                lambda **_: object(),
            ),
            patch(
                "src.module.chat_sessions.agent.calculator_mini_chat_agent.Runner.run_streamed",
                run_streamed,
            ),
        ):
            events = asyncio.run(collect())
        return events, captured, client

    def test_success_uses_exact_context_no_tools_one_turn_and_persists_before_finish(self):
        session = FakeSession()
        events, captured, client = self.run_agent(session, FakeStream())
        self.assertEqual(
            [event.type for event in events],
            [
                EventType.RUN_STARTED,
                EventType.TEXT_MESSAGE_START,
                EventType.TEXT_MESSAGE_CONTENT,
                EventType.TEXT_MESSAGE_CONTENT,
                EventType.TEXT_MESSAGE_END,
                EventType.RUN_FINISHED,
            ],
        )
        self.assertEqual(captured["agent"].instructions, INSTRUCTIONS)
        self.assertEqual(captured["agent"].tools, [])
        self.assertEqual(captured["kwargs"]["max_turns"], 1)
        run_config = captured["kwargs"]["run_config"]
        self.assertEqual(captured["agent"].model, "gpt-5-mini")
        self.assertEqual(run_config.model, "gpt-5-mini")
        self.assertEqual(run_config.workflow_name, "ConvFinQA document chat")
        self.assertEqual(run_config.group_id, "7")
        self.assertEqual(
            run_config.trace_metadata,
            {
                "dataset_conversation_id": "3",
                "chat_session_id": "7",
                "ag_ui_run_id": "run",
                "agent_variant": "direct-mini",
            },
        )
        self.assertFalse(run_config.trace_include_sensitive_data)
        self.assertEqual(
            run_config.tracing,
            {"include_task_and_turn_spans": True},
        )
        self.assertEqual(
            captured["input"],
            '<document_context>\n{"source":"full document"}\n</document_context>\n'
            "<user_question>\nquestion\n</user_question>",
        )
        messages = [value for value in session.added if isinstance(value, ChatMessageTable)]
        self.assertEqual(
            [(m.role, m.content) for m in messages],
            [("user", "question"), ("assistant", "Hello world")],
        )
        self.assertLess(
            session.sequence.index("commit", 4), session.sequence.index("TEXT_MESSAGE_END")
        )
        self.assertFalse(client.closed)

    def test_calculator_mini_uses_one_calculator_and_four_turns(self):
        session = FakeSession(agent_variant="calculator-mini")
        events, captured, _ = self.run_agent(
            session, FakeStream(), agent_type=CalculatorMiniChatAgent
        )
        self.assertEqual(events[-1].type, EventType.RUN_FINISHED)
        agent = captured["agent"]
        self.assertEqual(agent.name, "ConvFinQA calculator-mini document assistant")
        self.assertEqual(agent.model, "gpt-5-mini")
        self.assertEqual(agent.instructions, CALCULATOR_INSTRUCTIONS)
        self.assertEqual(agent.tools, [calculator])
        self.assertEqual(agent.model_settings.tool_choice, "required")
        self.assertFalse(agent.model_settings.parallel_tool_calls)
        self.assertEqual(captured["kwargs"]["max_turns"], 4)
        run_config = captured["kwargs"]["run_config"]
        self.assertEqual(run_config.model, "gpt-5-mini")
        self.assertEqual(run_config.workflow_name, "ConvFinQA calculator-mini document chat")
        self.assertEqual(run_config.trace_metadata["agent_variant"], "calculator-mini")
        self.assertEqual(
            captured["input"],
            '<document_context>\n{"source":"full document"}\n'
            "</document_context>\n<user_question>\nquestion\n</user_question>",
        )

    def test_calculator_tool_events_map_to_ag_ui_events(self):
        assistant = Agent(name="test calculator agent")
        raw_call = ResponseFunctionToolCall(
            arguments='{"operation":"subtract","a":-31,"b":-34}',
            call_id="call-1",
            name="calculator",
            type="function_call",
            status="completed",
        )
        stream = FakeStream(
            final_output="3 million",
            events=[
                RunItemStreamEvent(
                    name="tool_called", item=ToolCallItem(agent=assistant, raw_item=raw_call)
                ),
                RunItemStreamEvent(
                    name="tool_output",
                    item=ToolCallOutputItem(
                        agent=assistant,
                        raw_item={
                            "call_id": "call-1",
                            "output": "3",
                            "type": "function_call_output",
                        },
                        output=3,
                    ),
                ),
                SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(type="response.output_text.delta", delta="3 million"),
                ),
            ],
        )
        session = FakeSession(agent_variant="calculator-mini")
        events, _, _ = self.run_agent(session, stream, agent_type=CalculatorMiniChatAgent)

        relevant = [
            event
            for event in events
            if event.type
            in {
                EventType.TOOL_CALL_START,
                EventType.TOOL_CALL_ARGS,
                EventType.TOOL_CALL_END,
                EventType.TOOL_CALL_RESULT,
                EventType.TEXT_MESSAGE_CONTENT,
            }
        ]
        self.assertEqual(
            [event.type for event in relevant],
            [
                EventType.TOOL_CALL_START,
                EventType.TOOL_CALL_ARGS,
                EventType.TOOL_CALL_END,
                EventType.TOOL_CALL_RESULT,
                EventType.TEXT_MESSAGE_CONTENT,
            ],
        )
        start, args, end, result, content = relevant
        assistant_start = next(
            event for event in events if event.type == EventType.TEXT_MESSAGE_START
        )
        self.assertEqual(start.tool_call_id, "call-1")
        self.assertEqual(start.tool_call_name, "calculator")
        self.assertEqual(start.parent_message_id, assistant_start.message_id)
        self.assertEqual(args.tool_call_id, "call-1")
        self.assertEqual(args.delta, '{"operation":"subtract","a":-31,"b":-34}')
        self.assertEqual(end.tool_call_id, "call-1")
        self.assertEqual(result.tool_call_id, "call-1")
        self.assertEqual(result.content, "3")
        self.assertEqual(result.role, "tool")
        self.assertNotEqual(result.message_id, assistant_start.message_id)
        self.assertEqual(content.delta, "3 million")
        self.assertEqual(
            [(message.role, message.content) for message in session.added],
            [("user", "question"), ("assistant", "3 million")],
        )
        self.assertEqual(events[-1].type, EventType.RUN_FINISHED)

    def test_calculator_rejects_non_calculator_variant_without_runner(self):
        session = FakeSession(agent_variant="direct-mini")
        runner = patch(
            "src.module.chat_sessions.agent.calculator_mini_chat_agent.Runner.run_streamed"
        )

        async def collect():
            return [
                event
                async for event in self.agent(session, FakeClient(), CalculatorMiniChatAgent).run(
                    3, 7, request()
                )
            ]

        with runner as run_streamed:
            events = asyncio.run(collect())
        self.assertEqual(events[-1].code, "run_error")
        run_streamed.assert_not_called()
        self.assertEqual([message.role for message in session.added], ["user"])

    def test_calculator_operations_and_schema(self):
        calculate = cast(Any, calculator.on_invoke_tool)._get_wrapped_callable()
        self.assertEqual(
            calculator.params_json_schema["properties"]["operation"]["enum"],
            ["add", "subtract", "multiply", "divide"],
        )
        self.assertEqual(calculate("add", 2, 3), 5)
        self.assertEqual(calculate("subtract", 5, 2), 3)
        self.assertEqual(calculate("multiply", 2, 3), 6)
        self.assertEqual(calculate("divide", 6, 2), 3)
        with self.assertRaises(ValueError):
            calculate("divide", 1, 0)

    def test_empty_or_mismatched_final_output_is_error_without_assistant(self):
        for output in ("", "different"):
            with self.subTest(output=output):
                session = FakeSession()
                events, _, _ = self.run_agent(session, FakeStream(final_output=output))
                self.assertEqual(events[-1].type, EventType.RUN_ERROR)
                self.assertNotIn(EventType.TEXT_MESSAGE_END, [e.type for e in events])
                self.assertEqual([m.role for m in session.added], ["user"])

    def test_provider_failure_has_no_assistant(self):
        session = FakeSession()
        events, _, _ = self.run_agent(
            session, FakeStream(error=RuntimeError("secret provider error"))
        )
        self.assertEqual(events[-1].code, "run_error")
        self.assertNotIn("secret", events[-1].message)
        self.assertEqual([m.role for m in session.added], ["user"])

    def test_unknown_persisted_variant_is_run_error_without_runner_or_assistant(self):
        session = FakeSession(agent_variant="unknown")
        events, captured, _ = self.run_agent(session, FakeStream())
        self.assertEqual(events[-1].code, "run_error")
        self.assertEqual(captured, {})
        self.assertEqual([m.role for m in session.added], ["user"])

    def test_cancellation_cancels_stream_without_closing_client_and_has_no_assistant(self):
        session, stream = FakeSession(), FakeStream(error=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            self.run_agent(session, stream)
        self.assertTrue(stream.cancelled)
        self.assertFalse(self.last_client.closed)
        self.assertEqual([m.role for m in session.added], ["user"])

    def test_configuration_failure_occurs_after_user_persistence(self):
        session = FakeSession()

        async def collect():
            return [event async for event in self.agent(session).run(3, 7, request())]

        events = asyncio.run(collect())
        self.assertEqual(events[-1].code, "configuration_error")
        self.assertEqual([m.role for m in session.added], ["user"])

    def test_not_found(self):
        missing = asyncio.run(
            self._collect(self.agent(FakeSession(session=False)).run(3, 7, request()))
        )
        self.assertEqual(missing[0].code, "not_found")

    async def _collect(self, iterator):
        return [item async for item in iterator]
