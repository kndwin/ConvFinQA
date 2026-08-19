"""Small application-facing observability contracts."""

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Any, Protocol

from opentelemetry.trace import SpanKind


class Logger(Protocol):
    def debug(self, message: str, *, attributes: Mapping[str, Any] | None = None) -> None: ...

    def info(self, message: str, *, attributes: Mapping[str, Any] | None = None) -> None: ...

    def warning(self, message: str, *, attributes: Mapping[str, Any] | None = None) -> None: ...

    def error(self, message: str, *, attributes: Mapping[str, Any] | None = None) -> None: ...

    def exception(self, message: str, *, attributes: Mapping[str, Any] | None = None) -> None: ...


class Span(AbstractContextManager["Span"], Protocol):
    def set_attribute(self, name: str, value: Any) -> None: ...

    def record_exception(self, exception: BaseException) -> None: ...


class Tracer(Protocol):
    def span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Mapping[str, Any] | None = None,
    ) -> Span: ...


class Counter(Protocol):
    def add(
        self,
        value: int | float,
        attributes: Mapping[str, Any] | None = None,
    ) -> None: ...


class Histogram(Protocol):
    def record(
        self,
        value: int | float,
        attributes: Mapping[str, Any] | None = None,
    ) -> None: ...


class Meter(Protocol):
    def counter(self, name: str, *, unit: str = "", description: str = "") -> Counter: ...

    def histogram(self, name: str, *, unit: str = "", description: str = "") -> Histogram: ...

    def up_down_counter(self, name: str, *, unit: str = "", description: str = "") -> Counter: ...


class Observability(Protocol):
    logger: Logger
    tracer: Tracer
    meter: Meter

    def flush(self) -> bool: ...
