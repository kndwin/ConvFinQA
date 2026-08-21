import asyncio
import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from ag_ui.core import (
    AssistantMessage,
    UserMessage,
)

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.agent_execution.agent_execution_service import AgentExecutionService
from src.module.agent_execution.test_support import _FAKE_PROVIDER, FakeStream, request
from src.module.chat_sessions.chat_sessions_repository import ChatSessionRepository
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
    ChatSessionTable,
)
from src.platform.observability import NOOP_OBSERVABILITY, Observability


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
                self.calls.append(
                    ("create", params.dataset_conversation_id, params.agent_approach, params.model)
                )
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
            cast(AgentExecutionService, object()),
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
                    dataset_conversation_id=3,
                    agent_approach=AgentApproach.BASELINE,
                    model=OpenAIModel.GPT_5_6_SOL,
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
                ("create", 3, AgentApproach.BASELINE, OpenAIModel.GPT_5_6_SOL),
                ("update", 3, 8, "Title"),
                ("delete", 3, 8),
            ],
        )


class ChatSessionAgentExecutionTests(unittest.TestCase):
    async def _collect(self, iterator):
        return [event async for event in iterator]

    def _service(self, *, session=None, rows=(), sequence=None, dataset=True):
        sequence = sequence if sequence is not None else []
        session = session or ChatSessionTable(
            id=7,
            dataset_conversation_id=3,
            agent_approach="baseline",
            prompt_version="baseline:v1",
            context_version="document-conversation:v1",
            model="gpt-5.6-luna",
        )

        class ChatFake:
            async def get(self, params):
                return session

            async def messages(self, params):
                return rows

            async def persist_user_message(self, value, params):
                sequence.append(("user", params.content, params.client_message_id))

            async def persist_assistant_message(self, value, params):
                sequence.append(("assistant", params.content))

        class DatasetFake:
            async def get(self, params):
                return SimpleNamespace(doc_json="DOCUMENT") if dataset else None

        return ChatSessionService(
            cast(ChatSessionRepository, ChatFake()),
            cast(DatasetConversationRepository, DatasetFake()),
            cast(Observability, NOOP_OBSERVABILITY),
            AgentExecutionService(_FAKE_PROVIDER),
        ), sequence

    def test_not_found_is_not_found_and_does_not_invoke_runner(self):
        service, _ = self._service(dataset=False)
        with patch(
            "src.module.agent_execution.agent_approach.shared.base_agent_approach.Runner.run_streamed"
        ) as runner:
            events = asyncio.run(self._collect(service.run(3, 7, request())))
        self.assertEqual(events[-1].code, "not_found")
        runner.assert_not_called()

    def test_success_uses_canonical_db_transcript_and_persists_in_order(self):
        sequence = []
        rows = [
            SimpleNamespace(id=10, role="user", content="prior"),
            SimpleNamespace(id=11, role="assistant", content="canonical"),
        ]
        service, sequence = self._service(rows=rows, sequence=sequence)
        stream = FakeStream()
        captured = {}

        def run_streamed(*args, **kwargs):
            captured["context"] = args[1]
            self.assertEqual(sequence, [("user", "question", "client-message")])
            return stream

        with patch(
            "src.module.agent_execution.agent_approach.shared.base_agent_approach.Runner.run_streamed",
            side_effect=run_streamed,
        ):
            events = asyncio.run(
                self._collect(
                    service.run(
                        3,
                        7,
                        request(
                            [
                                UserMessage(id="client-message", content="question"),
                                AssistantMessage(id="golden", content="GOLDEN"),
                            ]
                        ),
                    )
                )
            )
        self.assertEqual(
            captured["context"],
            (
                "<conversation_history>\nuser: prior\nassistant: canonical\n"
                "</conversation_history>\n"
                "<document_context>\nDOCUMENT\n</document_context>\n"
                "<user_question>\nquestion\n</user_question>"
            ),
        )
        self.assertNotIn("GOLDEN", captured["context"])
        self.assertEqual(
            sequence, [("user", "question", "client-message"), ("assistant", "Hello world")]
        )
        self.assertEqual(events[-1].__class__.__name__, "RunFinishedEvent")

    def test_invalid_prompt_and_context_fail_before_user_persistence(self):
        for field, value in (
            ("prompt_version", "baseline-tool:v1"),
            ("context_version", "wrong:v1"),
        ):
            with self.subTest(field=field):
                session = ChatSessionTable(
                    id=7,
                    dataset_conversation_id=3,
                    agent_approach="baseline",
                    prompt_version="baseline:v1",
                    context_version="document-conversation:v1",
                    model="gpt-5.6-luna",
                )
                setattr(session, field, value)
                sequence = []
                service, _ = self._service(session=session, sequence=sequence)
                with patch(
                    "src.module.agent_execution.agent_approach.shared.base_agent_approach.Runner.run_streamed"
                ) as runner:
                    events = asyncio.run(self._collect(service.run(3, 7, request())))
                self.assertEqual(events[-1].code, "run_error")
                self.assertEqual(sequence, [])
                runner.assert_not_called()

    def test_cancellation_propagates_and_does_not_persist_assistant(self):
        sequence = []
        service, sequence = self._service(sequence=sequence)

        class SlowStream(FakeStream):
            async def stream_events(self):
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(type="response.output_text.delta", delta="partial"),
                )
                await asyncio.sleep(10)

        stream = SlowStream()

        async def exercise():
            with patch(
                "src.module.agent_execution.agent_approach.shared.base_agent_approach.Runner.run_streamed",
                return_value=stream,
            ):
                task = asyncio.create_task(self._collect(service.run(3, 7, request())))
                await asyncio.sleep(0)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

        asyncio.run(exercise())
        self.assertTrue(stream.cancelled)
        self.assertEqual([item[0] for item in sequence], ["user"])

    def test_list_form_uses_newest_nonblank_user_id_for_persistence(self):
        sequence = []
        service, sequence = self._service(sequence=sequence)
        with patch(
            "src.module.agent_execution.agent_approach.shared.base_agent_approach.Runner.run_streamed",
            return_value=FakeStream(),
        ):
            asyncio.run(
                self._collect(
                    service.run(
                        3,
                        7,
                        request(
                            [
                                UserMessage(id="old", content="old"),
                                UserMessage(id="blank", content=" "),
                                UserMessage(
                                    id="new", content=[{"type": "text", "text": " latest "}]
                                ),
                            ]
                        ),
                    )
                )
            )
        self.assertEqual(sequence[0], ("user", "latest", "new"))
