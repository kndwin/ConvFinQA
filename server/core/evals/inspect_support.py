"""Small adapter for recording externally executed usage in Inspect."""

from inspect_ai.model import ModelUsage

from evals.direct_schema import ObservedTurn


def record_application_usage(observations: tuple[ObservedTurn, ...]) -> None:
    """Bridge real application usage into Inspect's sample bookkeeping.

    Inspect 0.3.259 has no public API for externally executed completions.
    Keep this private API pin narrow because these helpers are version-sensitive.
    """
    from inspect_ai.model._model import sample_model_usage, set_model_usage

    usage_by_model: dict[str, ModelUsage] = {}
    for turn in observations:
        for usage in turn.model_usage:
            current = usage_by_model.get(usage.model, ModelUsage())
            usage_by_model[usage.model] = current + ModelUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                input_tokens_cache_read=usage.cached_input_tokens,
                input_tokens_cache_write=usage.cache_write_tokens,
                reasoning_tokens=usage.reasoning_tokens,
            )
    for model, usage in usage_by_model.items():
        set_model_usage(model, usage, sample_model_usage())
