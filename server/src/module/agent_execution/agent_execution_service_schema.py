from collections.abc import Mapping

from ag_ui.core import RunAgentInput
from pydantic import BaseModel, ConfigDict

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.agent_execution.agent_execution_runner_schema import PromptVersion


class AgentExecutionServiceRunParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    approach: AgentApproach
    prompt_version: str | None
    context_version: str
    model: OpenAIModel
    document: str
    input_data: RunAgentInput
    trace_metadata: Mapping[str, str]
    prompt_override: PromptVersion | None = None
