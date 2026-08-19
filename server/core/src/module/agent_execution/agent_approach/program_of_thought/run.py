import asyncio
import uuid
from collections.abc import AsyncIterator

from ag_ui.core import (
    BaseEvent,
    TextMessageContentEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from agents import RunResultStreaming
from openai import AsyncOpenAI

from src.module.agent_execution.agent_approach.program_of_thought.context.registry import (
    resolve as resolve_context,
)
from src.module.agent_execution.agent_approach.program_of_thought.prompts.registry import (
    resolve as resolve_prompt,
)
from src.module.agent_execution.agent_approach.shared.agent_definition import build_agent
from src.module.agent_execution.agent_approach.shared.tools.code_execution.provider import (
    CodeExecutionProvider,
)
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_runner_schema import (
    ApproachInput,
    PromptVersion,
    RenderedContext,
)
from src.module.agent_execution.execution.direct.agents_execution import AgentsApproach


class ProgramOfThoughtApproach(AgentsApproach):
    def __init__(
        self, client: AsyncOpenAI | None, execution_provider: CodeExecutionProvider
    ) -> None:
        super().__init__(client)
        self.execution_provider = execution_provider

    def resolve_prompt(self, prompt_id: str = "program-of-thought:v1") -> PromptVersion:
        return resolve_prompt(prompt_id)

    def render_context(
        self,
        version: str,
        document: str,
        transcript: tuple[ConversationMessage, ...],
        question: str,
    ) -> RenderedContext:
        return resolve_context(version, document, transcript, question)

    def stream(self, input_data: ApproachInput) -> AsyncIterator[BaseEvent]:
        # Retain custom providers for streaming normalization; the default OpenAI
        # provider has the same hosted Code Interpreter definition in the builder.
        agent, max_turns = build_agent(
            AgentApproach.PROGRAM_OF_THOUGHT,
            name="ConvFinQA program-of-thought document assistant",
            model=input_data.model,
            instructions=input_data.prompt.instructions,
        )
        if self.execution_provider.__class__.__name__ != "OpenAICodeExecutionProvider":
            agent.tools = [self.execution_provider.tool()]
        return self._events_with_code(
            input_data,
            self._stream(
                input_data, agent, max_turns, "ConvFinQA program-of-thought document chat"
            ),
        )

    async def _events_with_code(
        self, data: ApproachInput, stream: RunResultStreaming
    ) -> AsyncIterator[BaseEvent]:
        answer = ""
        started: set[str] = set()
        code_emitted: set[str] = set()
        full_code_emitted: set[str] = set()
        ended: set[str] = set()
        results: set[str] = set()

        try:
            async for event in stream.stream_events():
                update = None
                if event.type == "raw_response_event":
                    update = self.execution_provider.normalize_raw_event(event.data)
                else:
                    update = self.execution_provider.normalize_run_item_event(event)
                if update is not None and update.kind == "text_delta" and update.delta:
                    answer += update.delta
                    yield TextMessageContentEvent(
                        message_id=data.assistant_message_id, delta=update.delta
                    )
                elif update is not None and update.kind in {"call_started", "code_delta"}:
                    call_id = update.call_id
                    if call_id and call_id not in started:
                        started.add(call_id)
                        yield ToolCallStartEvent(
                            tool_call_id=call_id,
                            tool_call_name=update.tool_name or "",
                            parent_message_id=data.assistant_message_id,
                        )
                    if (
                        update.kind == "code_delta"
                        and call_id
                        and update.delta
                        and call_id not in full_code_emitted
                    ):
                        code_emitted.add(call_id)
                        yield ToolCallArgsEvent(tool_call_id=call_id, delta=update.delta)
                elif (
                    update is not None and update.kind == "snapshot" and update.snapshot is not None
                ):
                    snapshot = update.snapshot
                    call_id = snapshot.call_id
                    if call_id not in started:
                        started.add(call_id)
                        yield ToolCallStartEvent(
                            tool_call_id=call_id,
                            tool_call_name=snapshot.tool_name,
                            parent_message_id=data.assistant_message_id,
                        )
                    if snapshot.code and call_id not in code_emitted:
                        code_emitted.add(call_id)
                        full_code_emitted.add(call_id)
                        yield ToolCallArgsEvent(tool_call_id=call_id, delta=snapshot.code)
                    if snapshot.status == "completed" and call_id not in ended:
                        ended.add(call_id)
                        yield ToolCallEndEvent(tool_call_id=call_id)
                    if snapshot.output and call_id not in results:
                        results.add(call_id)
                        yield ToolCallResultEvent(
                            message_id=str(uuid.uuid4()),
                            tool_call_id=call_id,
                            content=snapshot.output,
                            role="tool",
                        )
                elif (
                    update is not None
                    and update.kind == "tool_output"
                    and update.call_id
                    and update.call_id not in results
                ):
                    results.add(update.call_id)
                    yield ToolCallResultEvent(
                        message_id=str(uuid.uuid4()),
                        tool_call_id=update.call_id,
                        content=update.output or "",
                        role="tool",
                    )
            if (
                not isinstance(stream.final_output, str)
                or not stream.final_output.strip()
                or answer != stream.final_output
            ):
                raise RuntimeError("Invalid final output")
            usage_event = self._model_usage_event(data, stream)
            if usage_event is not None:
                yield usage_event
        except asyncio.CancelledError, GeneratorExit:
            stream.cancel()
            raise
