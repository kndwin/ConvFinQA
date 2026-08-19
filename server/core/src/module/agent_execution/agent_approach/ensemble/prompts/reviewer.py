import hashlib
from pathlib import Path

from src.module.agent_execution.agent_execution_constants import (
    REVIEWER_PROMPT_VERSION,
    AgentApproach,
)
from src.module.agent_execution.agent_execution_runner_schema import PromptVersion

_TEXT = Path(__file__).with_name("ensemble-reviewer-v1.md").read_text().rstrip("\n")
V1 = PromptVersion(
    id=REVIEWER_PROMPT_VERSION,
    approach=AgentApproach.ENSEMBLE,
    instructions=_TEXT,
    content_hash=hashlib.sha256(_TEXT.encode()).hexdigest(),
)


def resolve(prompt_id: str = REVIEWER_PROMPT_VERSION) -> PromptVersion:
    if prompt_id != REVIEWER_PROMPT_VERSION:
        raise ValueError(f"Unsupported prompt version: {prompt_id}")
    return V1
