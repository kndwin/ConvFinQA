from typing import Literal

from agents import RunContextWrapper, function_tool

from .state import EvidenceToolState


@function_tool
def grounded_calculator(
    context: RunContextWrapper[EvidenceToolState],
    operation: Literal["select", "add", "subtract", "multiply", "divide", "greater", "exp"],
    operands: list[str],
) -> dict:
    """Calculate only from fetched evidence IDs, prior calc:N handles, or named constants.

    Never pass raw numeric literals as operands; fetch the evidence or
    use a named constant instead.
    """
    return context.context.calculate(operation, operands)
