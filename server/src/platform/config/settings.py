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
    logfire_environment: str = "development"
    openai_api_key: str | None = None
    otel_exporter_otlp_traces_protocol: str | None = None
    otel_exporter_otlp_traces_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None


config = Settings()
