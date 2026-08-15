from collections.abc import Mapping
from typing import Any

from opentelemetry.trace import SpanKind


class _Span:
    def __enter__(self) -> _Span:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def set_attribute(self, _name: str, _value: Any) -> None:
        pass

    def record_exception(self, _exception: BaseException) -> None:
        pass


class _Logger:
    def debug(self, *_args: object, **_kwargs: object) -> None:
        pass

    info = debug
    warning = debug
    error = debug
    exception = debug


class _Counter:
    def add(self, *_args: object, **_kwargs: object) -> None:
        pass


class _Histogram:
    def record(self, *_args: object, **_kwargs: object) -> None:
        pass


class _Meter:
    def counter(self, *_args: object, **_kwargs: object) -> _Counter:
        return _Counter()

    def histogram(self, *_args: object, **_kwargs: object) -> _Histogram:
        return _Histogram()

    def up_down_counter(self, *_args: object, **_kwargs: object) -> _Counter:
        return _Counter()


class _Tracer:
    def span(
        self,
        _name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Mapping[str, Any] | None = None,
    ) -> _Span:
        return _Span()


class NoopObservability:
    logger = _Logger()
    tracer = _Tracer()
    meter = _Meter()

    def flush(self) -> bool:
        return True


NOOP_OBSERVABILITY = NoopObservability()
