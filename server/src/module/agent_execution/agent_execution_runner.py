import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

from ag_ui.core import (
    BaseEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)

from src.module.agent_execution.agent_execution_constants import (
    DEFAULT_PROMPT_VERSIONS,
    AgentApproach,
)
from src.module.agent_execution.agent_execution_repository import AgentExecutionRepository
from src.module.agent_execution.agent_execution_runner_schema import (
    ApproachInput,
    ChatApproach,
)
from src.module.agent_execution.agent_execution_service_schema import AgentExecutionServiceRunParams
from src.module.agent_execution.agent_execution_util import newest_user_message


class AgentExecutionRunner:
    def __init__(self, baseline: ChatApproach, baseline_tool: ChatApproach) -> None:
        self.baseline, self.baseline_tool = baseline, baseline_tool

    def _approach(self, approach: AgentApproach) -> ChatApproach:
        match approach:
            case AgentApproach.BASELINE:
                return self.baseline
            case AgentApproach.BASELINE_TOOL:
                return self.baseline_tool
            case _:
                raise ValueError("Unsupported agent approach")

    async def run(
        self,
        params: AgentExecutionServiceRunParams,
        repository: AgentExecutionRepository,
    ) -> AsyncIterator[BaseEvent]:
        selected = newest_user_message(params.input_data)
        if selected is None:
            yield RunErrorEvent(message="A user message is required", code="invalid_input")
            return
        question, client_id = selected
        try:
            approach = self._approach(params.approach)
        except ValueError as error:
            yield RunErrorEvent(message=str(error), code="run_error")
            return
        if approach.client is None:
            yield RunErrorEvent(
                message="The assistant is not configured on the server",
                code="configuration_error",
            )
            return
        try:
            prior = tuple(await repository.messages())
            prompt = params.prompt_override or approach.resolve_prompt(
                params.prompt_version or DEFAULT_PROMPT_VERSIONS[params.approach]
            )
            if prompt.approach != params.approach:
                raise ValueError("Prompt version does not belong to selected agent approach")
            rendered = approach.render_context(
                params.context_version, params.document, prior, question
            )
        except (ValueError, OSError) as error:
            yield RunErrorEvent(message=str(error), code="run_error")
            return
        await repository.append_user(question, client_id)
        message_id = str(uuid4())
        answer = ""
        metadata = {
            **params.trace_metadata,
            "agent_approach": str(params.approach),
            "prompt_version": prompt.id,
            "prompt_hash": prompt.content_hash,
            "context_version": rendered.version.id,
            "context_hash": rendered.version.definition_hash,
            "model": str(params.model),
        }
        try:
            data = ApproachInput(
                prompt=prompt,
                context=rendered,
                model=params.model,
                trace_metadata=metadata,
                assistant_message_id=message_id,
                transcript=prior,
                question=question,
            )
            stream = approach.stream(data)
            yield RunStartedEvent(
                thread_id=params.input_data.thread_id, run_id=params.input_data.run_id
            )
            yield TextMessageStartEvent(message_id=message_id, role="assistant")
            async for event in stream:
                if isinstance(event, TextMessageContentEvent):
                    answer += event.delta
                yield event
            if not answer.strip():
                raise RuntimeError("Invalid final output")
            await repository.append_assistant(answer)
            yield TextMessageEndEvent(message_id=message_id)
            yield RunFinishedEvent(
                thread_id=params.input_data.thread_id, run_id=params.input_data.run_id
            )
        except asyncio.CancelledError, GeneratorExit:
            raise
        except ValueError as error:
            yield RunErrorEvent(message=str(error), code="run_error")
        except Exception:
            yield RunErrorEvent(
                message="The assistant could not complete this run", code="run_error"
            )
