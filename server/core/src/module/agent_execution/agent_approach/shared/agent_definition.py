"""Pure, workflow-safe definitions for the supported Agents SDK approaches."""

from agents import Agent, CodeInterpreterTool, ModelSettings
from src.module.agent_execution.agent_approach.baseline_tool.tools.calculator import calculator
from src.module.agent_execution.agent_execution_constants import AgentApproach


def build_agent(
    approach: AgentApproach,
    *,
    name: str,
    instructions: str,
    model: str,
) -> tuple[Agent, int]:
    """Build an approach agent without clients, providers, or other I/O."""
    if approach is AgentApproach.ENSEMBLE:
        raise ValueError("An ensemble cannot be used as an individual agent")
    if approach is AgentApproach.BASELINE:
        return Agent(name=name, instructions=instructions, model=model, tools=[]), 1
    if approach is AgentApproach.BASELINE_TOOL:
        return (
            Agent(
                name=name,
                instructions=instructions,
                model=model,
                tools=[calculator],
                model_settings=ModelSettings(tool_choice="required", parallel_tool_calls=False),
            ),
            4,
        )
    if approach is AgentApproach.PROGRAM_OF_THOUGHT:
        return (
            Agent(
                name=name,
                instructions=instructions,
                model=model,
                tools=[
                    CodeInterpreterTool({"type": "code_interpreter", "container": {"type": "auto"}})
                ],
                model_settings=ModelSettings(tool_choice="required", parallel_tool_calls=False),
            ),
            4,
        )
    raise ValueError(f"Unsupported agent approach: {approach}")
