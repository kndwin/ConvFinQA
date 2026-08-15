from collections.abc import Mapping
from threading import Lock
from typing import Any, cast

from fastapi import FastAPI
from opentelemetry.trace import SpanKind
from sqlalchemy.ext.asyncio import AsyncEngine

from .contracts import Logger, Meter, Observability, Span, Tracer


class _LogfireLogger(Logger):
    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def _log(
        self,
        level: str,
        message: str,
        attributes: Mapping[str, Any] | None,
        *,
        exc_info: bool = False,
    ) -> None:
        self._backend.log(
            level,
            message,
            attributes=dict(attributes or {}),
            exc_info=exc_info,
        )

    def debug(self, message: str, *, attributes=None) -> None:
        self._log("debug", message, attributes)

    def info(self, message: str, *, attributes=None) -> None:
        self._log("info", message, attributes)

    def warning(self, message: str, *, attributes=None) -> None:
        self._log("warning", message, attributes)

    def error(self, message: str, *, attributes=None) -> None:
        self._log("error", message, attributes)

    def exception(self, message: str, *, attributes=None) -> None:
        self._log("error", message, attributes, exc_info=True)


class _LogfireTracer(Tracer):
    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Mapping[str, Any] | None = None,
    ) -> Span:
        return cast(
            Span,
            self._backend.span(
                name,
                _span_name=name,
                _span_kind=kind,
                **dict(attributes or {}),
            ),
        )


class _LogfireMeter(Meter):
    def __init__(self, backend: Any) -> None:
        self._backend = backend
        self._instruments: dict[tuple[str, str, str, str], Any] = {}
        self._lock = Lock()

    def _get(self, kind: str, name: str, unit: str, description: str) -> Any:
        key = (kind, name, unit, description)
        with self._lock:
            instrument = self._instruments.get(key)
            if instrument is None:
                factory = getattr(self._backend, f"metric_{kind}")
                instrument = factory(name, unit=unit, description=description)
                self._instruments[key] = instrument
        return instrument

    def counter(self, name: str, *, unit: str = "", description: str = "") -> Any:
        return self._get("counter", name, unit, description)

    def histogram(self, name: str, *, unit: str = "", description: str = "") -> Any:
        return self._get("histogram", name, unit, description)

    def up_down_counter(self, name: str, *, unit: str = "", description: str = "") -> Any:
        return self._get("up_down_counter", name, unit, description)


class LogfireObservability(Observability):
    def __init__(self, backend: Any) -> None:
        self.logger = _LogfireLogger(backend)
        self.tracer = _LogfireTracer(backend)
        self.meter = _LogfireMeter(backend)
        self._backend = backend

    def flush(self) -> bool:
        return bool(self._backend.force_flush())

    def instrument_fastapi(self, app: FastAPI) -> None:
        self._backend.instrument_fastapi(
            app, capture_headers=False, record_send_receive=False, extra_spans=False
        )

    def instrument_sqlalchemy(self, engine: AsyncEngine) -> None:
        self._backend.instrument_sqlalchemy(engine=engine)
