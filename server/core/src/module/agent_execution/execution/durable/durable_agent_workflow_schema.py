"""Serializable contracts for reusable single-agent durable execution."""

from pydantic import BaseModel, ConfigDict


class DurableAgentWorkflowInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    # Defaults keep payloads written by the initial durable proof readable.
    approach: str = "baseline"
    model: str
    agent_name: str
    instructions: str
    rendered_context: str
    trace_metadata: dict[str, str]
    max_turns: int = 0
    prompt_version: str = ""
    prompt_hash: str = ""
    context_version: str = ""
    context_hash: str = ""
    stream: bool = False


class DurableAgentWorkflowResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    final_output: str
    approach: str = "baseline"
    duration_ms: int = 0
    prompt_version: str = ""
    prompt_hash: str = ""
    context_version: str = ""
    context_hash: str = ""
