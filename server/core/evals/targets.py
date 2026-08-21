from src.module.agent_execution.agent_approach.baseline.prompts.registry import resolve as baseline
from src.module.agent_execution.agent_approach.baseline_tool.prompts.registry import (
    resolve as baseline_tool,
)
from src.module.agent_execution.agent_approach.evidence.prompts.registry import resolve as evidence
from src.module.agent_execution.agent_approach.program_of_thought.prompts.registry import (
    resolve as program_of_thought,
)
from src.module.agent_execution.agent_approach.shared.context.document_conversation import VERSION

from evals.benchmarks.convfinqa.selector_prompt import EVIDENCE_SELECTOR_V1
from evals.targets_schema import TargetSpec

RESOLVERS = {
    "baseline:v1": baseline,
    "baseline-tool:v1": baseline_tool,
    "program-of-thought:v1": program_of_thought,
    "baseline:v2": baseline,
    "baseline-tool:v2": baseline_tool,
    "program-of-thought:v2": program_of_thought,
    "baseline:v3": baseline,
    "evidence:v1": evidence,
    "program-of-thought:v3": program_of_thought,
}


def resolve_target(target_id: str) -> TargetSpec:
    try:
        prompt = RESOLVERS[target_id](target_id)
    except KeyError as exc:
        raise ValueError(f"Unsupported evaluation target: {target_id}") from exc
    context_version = VERSION.id
    context_hash = VERSION.definition_hash
    if target_id == "evidence:v1":
        from src.module.agent_execution.agent_approach.evidence.context.registry import (
            CONTEXT_VERSION,
        )
        from src.module.agent_execution.agent_approach.evidence.context.registry import (
            VERSION as EVIDENCE_CONTEXT_VERSION,
        )

        context_version = CONTEXT_VERSION
        context_hash = EVIDENCE_CONTEXT_VERSION.definition_hash
    spec = TargetSpec(
        id=target_id,
        approach=prompt.approach,
        prompt=prompt,
        context_version=context_version,
        context_hash=context_hash,
    )
    return spec


def component_metadata(target_id: str) -> dict[str, str]:
    """Reproducibility metadata for every prompt participating in a target."""
    target = resolve_target(target_id)
    data = {
        "action_prompt_version": target.prompt.id,
        "action_prompt_hash": target.prompt.content_hash,
    }
    if target_id == "program-of-thought:v3":
        data.update(
            evidence_prompt_version=EVIDENCE_SELECTOR_V1.id,
            evidence_prompt_hash=EVIDENCE_SELECTOR_V1.content_hash,
        )
    elif target_id == "evidence:v1":
        # Evidence is a first-class approach; this records its own prompt,
        # not the eval-only staged selector.
        data.update(
            evidence_prompt_version=target.prompt.id,
            evidence_prompt_hash=target.prompt.content_hash,
        )
    return data
