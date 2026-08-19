import inspect
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, TypeVar, cast

from opentelemetry.trace import SpanKind

F = TypeVar("F", bound=Callable[..., Any])


def trace_method(
    name: str,
    *,
    span_kind: SpanKind = SpanKind.INTERNAL,
    attributes: Mapping[str, Any] | None = None,
) -> Callable[[F], F]:
    """Trace an instance method without inspecting its arguments or result."""
    static_attributes = dict(attributes or {})

    def decorate(function: F) -> F:
        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                with self.observability.tracer.span(
                    name,
                    kind=span_kind,
                    attributes=static_attributes,
                ):
                    return await function(self, *args, **kwargs)

            return cast(F, async_wrapper)

        @wraps(function)
        def sync_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            with self.observability.tracer.span(
                name,
                kind=span_kind,
                attributes=static_attributes,
            ):
                return function(self, *args, **kwargs)

        return cast(F, sync_wrapper)

    return decorate
