"""Settings loaded from the environment and the local .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        str_strip_whitespace=True,
    )

    database_url: str | None = None
    cors_origins: str = ""
    logfire_environment: str = "development"
    openai_api_key: str | None = None
    otel_exporter_otlp_traces_protocol: str | None = None
    otel_exporter_otlp_traces_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None


config = Settings()


def async_database_url(url: str | None) -> str | None:
    """Normalize Railway's plain PostgreSQL URL for SQLAlchemy asyncpg."""
    if url is None or "+" in url.split(":", 1)[0]:
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    return url
