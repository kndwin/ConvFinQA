from src.module.agent_execution.agent_approach.baseline.prompts.registry import (
    resolve as baseline,
)
from src.module.agent_execution.agent_approach.baseline_tool.prompts.registry import (
    resolve as baseline_tool,
)
from src.module.agent_execution.agent_approach.program_of_thought.prompts.registry import (
    resolve as program_of_thought,
)
from src.module.agent_execution.agent_approach.shared.context.document_conversation import VERSION

from evals.models_schema import TargetSpec

RESOLVERS = {
    "baseline:v1": baseline,
    "baseline-tool:v1": baseline_tool,
    "program-of-thought:v1": program_of_thought,
}


def resolve_target(target_id: str) -> TargetSpec:
    try:
        prompt = RESOLVERS[target_id](target_id)
    except KeyError as exc:
        raise ValueError(f"Unsupported evaluation target: {target_id}") from exc
    return TargetSpec(
        id=target_id,
        approach=prompt.approach,
        prompt=prompt,
        context_version=VERSION.id,
        context_hash=VERSION.definition_hash,
    )
