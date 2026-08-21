"""Eval-only staged selector prompt; production baseline owns no selector."""

# ruff: noqa: E501,I001
import hashlib
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.agent_execution_runner_schema import PromptVersion

_TEXT = (
    "Select relevant evidence IDs only. Return JSON with an evidence_ids array and no other fields."
)
EVIDENCE_SELECTOR_V1 = PromptVersion(
    id="evidence-selector:v1",
    approach=AgentApproach.BASELINE,
    instructions=_TEXT,
    content_hash=hashlib.sha256(_TEXT.encode()).hexdigest(),
)
