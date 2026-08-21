import asyncio
import unittest

from src.module.agent_execution.agent_execution_repository import (
    CallbackAgentExecutionRepository,
    InMemoryAgentExecutionRepository,
)
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage


class AgentExecutionRepositoryTests(unittest.TestCase):
    def test_in_memory_preserves_exact_ids_and_order(self):
        repository = InMemoryAgentExecutionRepository()

        async def exercise():
            await repository.append_user("first", "client-1")
            await repository.append_assistant("answer")
            await repository.append_user("second", None)
            return await repository.messages()

        self.assertEqual(
            asyncio.run(exercise()),
            (
                ConversationMessage(role="user", content="first", message_id="client-1"),
                ConversationMessage(role="assistant", content="answer"),
                ConversationMessage(role="user", content="second"),
            ),
        )

    def test_callback_repository_invokes_all_callbacks_with_exact_arguments(self):
        calls = []

        async def messages():
            calls.append(("messages",))
            return (ConversationMessage(role="user", content="old", message_id="old-id"),)

        async def append_user(content, client_message_id):
            calls.append(("user", content, client_message_id))

        async def append_assistant(content):
            calls.append(("assistant", content))

        repository = CallbackAgentExecutionRepository(messages, append_user, append_assistant)

        async def exercise():
            history = await repository.messages()
            await repository.append_user("new", "new-id")
            await repository.append_assistant("result")
            return history

        self.assertEqual(
            asyncio.run(exercise()),
            (ConversationMessage(role="user", content="old", message_id="old-id"),),
        )
        self.assertEqual(
            calls,
            [("messages",), ("user", "new", "new-id"), ("assistant", "result")],
        )
