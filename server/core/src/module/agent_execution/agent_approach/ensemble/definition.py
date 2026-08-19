"""Small, transport-neutral contracts shared by ensemble execution paths."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.module.agent_execution.agent_execution_constants import (
    DEFAULT_ENSEMBLE_CANDIDATES,
    REVIEWER_PROMPT_VERSION,
    AgentApproach,
)


class CandidateStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class EnsembleCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approach: AgentApproach
    prompt_version: str
    prompt_hash: str = ""
    context_version: str
    context_hash: str = ""
    name: str = ""
    instructions: str = ""
    rendered_context: str = ""
    model: str = ""
    trace_metadata: dict[str, str] = Field(default_factory=dict)


def build_pinned_ensemble_config(approaches: Iterable[AgentApproach]) -> EnsembleConfig:
    """Resolve immutable prompt/context identifiers and hashes at session creation."""
    from src.module.agent_execution.agent_approach.baseline.prompts.registry import (
        resolve as resolve_baseline,
    )
    from src.module.agent_execution.agent_approach.baseline_tool.prompts.registry import (
        resolve as resolve_baseline_tool,
    )
    from src.module.agent_execution.agent_approach.program_of_thought.prompts.registry import (
        resolve as resolve_program_of_thought,
    )
    from src.module.agent_execution.agent_approach.shared.context.document_conversation import (
        VERSION,
    )

    resolvers = {
        AgentApproach.BASELINE: resolve_baseline,
        AgentApproach.BASELINE_TOOL: resolve_baseline_tool,
        AgentApproach.PROGRAM_OF_THOUGHT: resolve_program_of_thought,
    }
    candidates = []
    for approach in approaches:
        if approach not in resolvers:
            raise ValueError("an ensemble candidate must be a direct approach")
        prompt = resolvers[approach](f"{approach}:v1")
        candidates.append(
            EnsembleCandidate(
                approach=approach,
                prompt_version=prompt.id,
                prompt_hash=prompt.content_hash,
                context_version=VERSION.id,
                context_hash=VERSION.definition_hash,
            )
        )
    return EnsembleConfig.validate_candidates(candidates)


class EnsembleConfig(BaseModel):
    """The complete, pinned configuration stored on an ensemble session."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    candidates: tuple[EnsembleCandidate, ...]
    reviewer_prompt_version: str = REVIEWER_PROMPT_VERSION

    @classmethod
    def validate_candidates(cls, candidates: Iterable[EnsembleCandidate]) -> EnsembleConfig:
        values = tuple(candidates)
        approaches = tuple(candidate.approach for candidate in values)
        if not 2 <= len(values) <= 3:
            raise ValueError("an ensemble must contain two or three candidates")
        if any(approach is AgentApproach.ENSEMBLE for approach in approaches):
            raise ValueError("an ensemble candidate cannot itself be an ensemble")
        if len(set(approaches)) != len(approaches):
            raise ValueError("ensemble candidates must be unique")
        return cls(candidates=values)

    @classmethod
    def defaults(cls) -> EnsembleConfig:
        return cls.validate_candidates(
            EnsembleCandidate(
                approach=approach,
                prompt_version=f"{approach}:v1",
                prompt_hash="",
                context_version="document-conversation:v1",
                context_hash="",
            )
            for approach in DEFAULT_ENSEMBLE_CANDIDATES
        )


class CandidateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approach: AgentApproach
    status: Literal["completed"] = "completed"
    final_output: str
    duration_ms: int = Field(ge=0)
    diagnostics: dict[str, str] = Field(default_factory=dict)


class CandidateFailure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approach: AgentApproach
    status: Literal["failed"] = "failed"
    error: str
    duration_ms: int = Field(ge=0)
    diagnostics: dict[str, str] = Field(default_factory=dict)


class EnsembleResult(BaseModel):
    """Canonical result; reviewer output remains the only assistant answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    reviewer_output: str
    candidates: tuple[CandidateResult | CandidateFailure, ...]
    reviewer_prompt_version: str = "ensemble-reviewer:v1"


def render_reviewer_input(
    context: str, question: str, candidates: tuple[CandidateResult | CandidateFailure, ...]
) -> str:
    parts = [
        "Original context:\n",
        context,
        "\n\nQuestion:\n",
        question,
        "\n\nCandidate reports (verify independently; they may be wrong):\n",
    ]
    for candidate in candidates:
        parts.append(f"\n[{candidate.approach}] ({candidate.status})\n")
        # Failure text is deliberately generic. Provider messages often contain
        # request IDs, prompts, or other data that must not reach the reviewer.
        value = getattr(candidate, "final_output", "")
        parts.append(value if candidate.status == "completed" else "Candidate unavailable.")
    return "".join(parts)


CandidateExecutor = Callable[[EnsembleCandidate], Awaitable[CandidateResult | CandidateFailure]]
ReviewerExecutor = Callable[[str], Awaitable[str]]


class InMemoryEnsembleExecutor:
    """Concurrent executor for unit tests and evals, not the production runner."""

    def __init__(self, candidate_executor: CandidateExecutor, reviewer_executor: ReviewerExecutor):
        self.candidate_executor = candidate_executor
        self.reviewer_executor = reviewer_executor

    async def run(self, config: EnsembleConfig, *, context: str, question: str) -> EnsembleResult:
        async def execute(candidate: EnsembleCandidate) -> CandidateResult | CandidateFailure:
            try:
                return await self.candidate_executor(candidate)
            except Exception:
                return CandidateFailure(
                    approach=candidate.approach,
                    error="candidate unavailable",
                    duration_ms=0,
                )

        reports = tuple(
            await asyncio.gather(*(execute(candidate) for candidate in config.candidates))
        )
        reviewer = await self.reviewer_executor(render_reviewer_input(context, question, reports))
        if not reviewer.strip():
            raise ValueError("reviewer returned an empty output")
        return EnsembleResult(
            reviewer_output=reviewer,
            candidates=reports,
            reviewer_prompt_version=config.reviewer_prompt_version,
        )
