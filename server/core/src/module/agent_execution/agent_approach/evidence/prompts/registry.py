import hashlib
from pathlib import Path

from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_runner_schema import PromptVersion

_TEXT = (Path(__file__).with_name("v1.md")).read_text().rstrip("\n")
V1 = PromptVersion(
    id="evidence:v1",
    approach=AgentApproach.EVIDENCE,
    instructions=_TEXT,
    content_hash=hashlib.sha256(_TEXT.encode()).hexdigest(),
)


def resolve(prompt_id: str = "evidence:v1") -> PromptVersion:
    if prompt_id != V1.id:
        raise ValueError(f"Unsupported prompt version: {prompt_id}")
    return V1
