from agents import RunContextWrapper, function_tool

from .state import EvidenceToolState


@function_tool
def evidence_fetch(
    context: RunContextWrapper[EvidenceToolState], query: str, max_results: int = 5
) -> dict:
    """Fetch 1 to 10 matching private-document evidence items.

    ``max_results`` must be between 1 and 10 inclusive. Use returned
    evidence IDs as operands for grounded_calculator.
    """
    return context.context.fetch(query, max_results)
