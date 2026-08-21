"""Runtime-state-dependent validation for evidence answers."""

from decimal import ROUND_HALF_UP, Decimal

from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, output_guardrail

from .structured_output import EvidenceAnswer
from .tools import EvidenceToolState


@output_guardrail
def evidence_output_guardrail(
    context: RunContextWrapper[EvidenceToolState],
    _agent: Agent[EvidenceToolState],
    output: EvidenceAnswer,
) -> GuardrailFunctionOutput:
    """Ensure the answer is supported by work performed during this run."""
    state = context.context
    if not state.successful_fetches:
        return GuardrailFunctionOutput(
            output_info="A nonempty evidence fetch is required", tripwire_triggered=True
        )
    if output.kind == "number":
        if output.result_ref not in state.results:
            return GuardrailFunctionOutput(
                output_info="Numeric answer result_ref is not a calculator result",
                tripwire_triggered=True,
            )
        declared = Decimal(output.value)
        if output.representation == "percent":
            declared /= Decimal(100)
        quantum = Decimal("0.00001")
        if declared.quantize(quantum, rounding=ROUND_HALF_UP) != state.results[
            output.result_ref
        ].quantize(quantum, rounding=ROUND_HALF_UP):
            return GuardrailFunctionOutput(
                output_info="Numeric answer does not match result_ref", tripwire_triggered=True
            )
    return GuardrailFunctionOutput(
        output_info="Evidence answer is grounded", tripwire_triggered=False
    )
