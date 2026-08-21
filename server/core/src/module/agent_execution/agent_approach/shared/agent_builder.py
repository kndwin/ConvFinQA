"""Provider-neutral construction of Agents SDK agents."""

from collections.abc import Sequence
from typing import Any

from agents import Agent, ModelSettings, OutputGuardrail
from agents.tool import Tool


def build_agent(
    *,
    name: str,
    instructions: str,
    model: str,
    tools: Sequence[Tool] = (),
    require_tool: bool = False,
    output_type: type[object] | None = None,
    output_guardrails: Sequence[OutputGuardrail[Any]] = (),
) -> Agent:
    """Build an agent without clients, providers, or other I/O."""
    settings = (
        ModelSettings(tool_choice="required", parallel_tool_calls=False)
        if require_tool
        else ModelSettings()
    )
    return Agent(
        name=name,
        instructions=instructions,
        model=model,
        tools=list(tools),
        model_settings=settings,
        output_type=output_type,
        output_guardrails=list(output_guardrails),
    )
