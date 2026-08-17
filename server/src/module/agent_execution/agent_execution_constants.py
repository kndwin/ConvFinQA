from enum import StrEnum


class AgentApproach(StrEnum):
    BASELINE = "baseline"
    BASELINE_TOOL = "baseline-tool"
    PROGRAM_OF_THOUGHT = "program-of-thought"


DEFAULT_PROMPT_VERSIONS: dict[AgentApproach, str] = {
    AgentApproach.BASELINE: "baseline:v1",
    AgentApproach.BASELINE_TOOL: "baseline-tool:v1",
    AgentApproach.PROGRAM_OF_THOUGHT: "program-of-thought:v1",
}
DEFAULT_CONTEXT_VERSION = "document-conversation:v1"


class OpenAIModel(StrEnum):
    GPT_5_6_LUNA = "gpt-5.6-luna"
    GPT_5_6_TERRA = "gpt-5.6-terra"
    GPT_5_6_SOL = "gpt-5.6-sol"
    GPT_5_MINI = "gpt-5-mini"
