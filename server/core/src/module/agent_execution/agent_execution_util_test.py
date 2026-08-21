import unittest
from typing import cast

from ag_ui.core import (
    RunAgentInput,
    UserMessage,
)

from src.module.agent_execution.agent_execution_util import newest_user_message


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
        selected = cast(tuple[str, str | None], newest_user_message(input_data))
        self.assertEqual(selected[0], "new question")

    def test_missing_user_message(self) -> None:
        self.assertIsNone(newest_user_message(request([])))
