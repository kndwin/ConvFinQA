"""Non-durable ensemble transport used by evaluation and local tests."""

import asyncio
import time

from agents import Agent, RunConfig, Runner
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI

from src.module.agent_execution.agent_approach.ensemble.definition import (
    CandidateFailure,
    CandidateResult,
    EnsembleResult,
    render_reviewer_input,
)
from src.module.agent_execution.agent_approach.ensemble.prompts.reviewer import (
    resolve as resolve_reviewer,
)
from src.module.agent_execution.agent_approach.shared.agent_definition import build_agent
from src.module.agent_execution.agent_execution_constants import (
    DEFAULT_CONTEXT_VERSION,
    DEFAULT_ENSEMBLE_CANDIDATES,
    DEFAULT_PROMPT_VERSIONS,
    REVIEWER_PROMPT_VERSION,
    AgentApproach,
    OpenAIModel,
)
from src.module.agent_execution.agent_execution_repository_schema import ConversationMessage
from src.module.agent_execution.agent_execution_service import AgentExecutionService


async def run_direct_ensemble(
    *,
    service: AgentExecutionService,
    client: AsyncOpenAI,
    document: str,
    transcript: tuple[ConversationMessage, ...],
    question: str,
    model: OpenAIModel,
    trace_metadata: dict[str, str],
) -> EnsembleResult:
    """Run the fixed three-candidate ensemble without Temporal or streaming."""

    provider = OpenAIProvider(openai_client=client)

    async def candidate(approach: AgentApproach) -> CandidateResult | CandidateFailure:
        started = time.perf_counter()
        try:
            implementation = service.resolve_approach(approach)
            prompt = implementation.resolve_prompt(DEFAULT_PROMPT_VERSIONS[approach])
            context = implementation.render_context(
                DEFAULT_CONTEXT_VERSION, document, transcript, question
            )
            agent, max_turns = build_agent(
                approach,
                name=f"ConvFinQA {approach} ensemble candidate",
                instructions=prompt.instructions,
                model=str(model),
            )
            result = await Runner.run(
                agent,
                context.rendered,
                max_turns=max_turns,
                run_config=RunConfig(
                    model_provider=provider,
                    workflow_name=f"ensemble-candidate-{approach}",
                    trace_metadata={**trace_metadata, "candidate_approach": str(approach)},
                    trace_include_sensitive_data=False,
                ),
            )
            output = result.final_output
            if not isinstance(output, str) or not output.strip():
                raise ValueError("candidate returned an invalid final output")
            return CandidateResult(
                approach=approach,
                final_output=output,
                duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            )
        except Exception:
            return CandidateFailure(
                approach=approach,
                error="candidate unavailable",
                duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            )

    candidates = tuple(
        await asyncio.gather(*(candidate(approach) for approach in DEFAULT_ENSEMBLE_CANDIDATES))
    )
    reviewer_prompt = resolve_reviewer(REVIEWER_PROMPT_VERSION)
    reviewer = Agent(
        name="Ensemble independent reviewer",
        instructions=reviewer_prompt.instructions,
        model=str(model),
        tools=[],
    )
    result = await Runner.run(
        reviewer,
        render_reviewer_input(document, question, candidates),
        run_config=RunConfig(
            model_provider=provider,
            workflow_name="ensemble-reviewer",
            trace_metadata=trace_metadata,
            trace_include_sensitive_data=False,
        ),
    )
    output = result.final_output
    if not isinstance(output, str) or not output.strip():
        raise RuntimeError("reviewer returned an invalid final output")
    return EnsembleResult(
        reviewer_output=output,
        candidates=candidates,
        reviewer_prompt_version=reviewer_prompt.id,
    )
