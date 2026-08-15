"""Bootstrap the configured observability backend."""

import os
from contextlib import asynccontextmanager
from functools import cache
from typing import cast

import logfire
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from src.platform.config import Settings, config

from .logfire_adapter import LogfireObservability
from .provider import get_observability, set_observability

_instrumented_apps: set[int] = set()
_instrumented_engines: set[int] = set()


def _bridge_otel_environment(settings: Settings) -> None:
    """Expose OTLP settings to libraries that read directly from the environment."""
    variables = {
        "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": settings.otel_exporter_otlp_traces_protocol,
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": settings.otel_exporter_otlp_traces_endpoint,
        "OTEL_EXPORTER_OTLP_HEADERS": settings.otel_exporter_otlp_headers,
    }
    for name, value in variables.items():
        if value is not None and value.strip():
            os.environ.setdefault(name, value)


@cache
def _initialize_observability() -> None:
    """Initialize the configured observability backend once."""
    _bridge_otel_environment(config)
    backend = logfire.configure(
        send_to_logfire="if-token-present",
        service_name="openai-deploy-api",
        service_version="0.1.0",
        environment=config.logfire_environment,
        inspect_arguments=False,
    )
    logfire.instrument_openai_agents()
    set_observability(LogfireObservability(backend))


def configure_observability(app: FastAPI, engine: AsyncEngine) -> None:
    """Configure Logfire, then install instrumentation for the app and database."""
    _initialize_observability()
    observability = cast(LogfireObservability, get_observability())
    if id(app) not in _instrumented_apps:
        observability.instrument_fastapi(app)
        _instrumented_apps.add(id(app))
    if id(engine) not in _instrumented_engines:
        observability.instrument_sqlalchemy(engine)
        _instrumented_engines.add(id(engine))


def flush_observability() -> bool:
    """Flush pending observability data."""
    return get_observability().flush()


@asynccontextmanager
async def observability_lifespan():
    """Configure observability for the application and flush it on shutdown."""
    try:
        _initialize_observability()
        yield
    finally:
        flush_observability()
