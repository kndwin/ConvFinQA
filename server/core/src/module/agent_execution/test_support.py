from types import SimpleNamespace
from typing import cast

from ag_ui.core import RunAgentInput, UserMessage
from agents.models.interface import ModelProvider


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


_FAKE_PROVIDER = cast(ModelProvider, object())
