import hashlib
from pathlib import Path

from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_runner_schema import PromptVersion

_ID = "program-of-thought:v1"
_TEXT = (Path(__file__).with_name("v1.md")).read_text().rstrip("\n")
V1 = PromptVersion(
    id=_ID,
    approach=AgentApproach.PROGRAM_OF_THOUGHT,
    instructions=_TEXT,
    content_hash=hashlib.sha256(_TEXT.encode()).hexdigest(),
)


def resolve(prompt_id: str = _ID) -> PromptVersion:
    if prompt_id != _ID:
        raise ValueError(f"Unsupported prompt version: {prompt_id}")
    return V1
