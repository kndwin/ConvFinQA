import hashlib
from pathlib import Path

from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_runner_schema import PromptVersion

_ID = "baseline:v1"
_TEXT = (Path(__file__).with_name("v1.md")).read_text().rstrip("\n")
V1 = PromptVersion(
    id=_ID,
    approach=AgentApproach.BASELINE,
    instructions=_TEXT,
    content_hash=hashlib.sha256(_TEXT.encode()).hexdigest(),
)
_V2_ID = "baseline:v2"
_V2_TEXT = (Path(__file__).with_name("v2.md")).read_text().rstrip("\n")
V2 = PromptVersion(
    id=_V2_ID,
    approach=AgentApproach.BASELINE,
    instructions=_V2_TEXT,
    content_hash=hashlib.sha256(_V2_TEXT.encode()).hexdigest(),
)
_V3_ID = "baseline:v3"
_V3_TEXT = (Path(__file__).with_name("v3.md")).read_text().rstrip("\n")
V3 = PromptVersion(
    id=_V3_ID,
    approach=AgentApproach.BASELINE,
    instructions=_V3_TEXT,
    content_hash=hashlib.sha256(_V3_TEXT.encode()).hexdigest(),
)


def resolve(prompt_id: str = _ID) -> PromptVersion:
    if prompt_id == _ID:
        return V1
    if prompt_id == _V2_ID:
        return V2
    if prompt_id == _V3_ID:
        return V3
    if prompt_id != _ID:
        raise ValueError(f"Unsupported prompt version: {prompt_id}")
