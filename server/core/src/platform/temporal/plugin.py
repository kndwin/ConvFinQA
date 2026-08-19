"""Configuration for the official Temporal OpenAI Agents integration."""

from datetime import timedelta

from agents import ModelProvider
from temporalio.common import RetryPolicy
from temporalio.contrib.openai_agents import ModelActivityParameters, OpenAIAgentsPlugin

from src.platform.config.settings import Settings


def create_model_activity_parameters(settings: Settings) -> ModelActivityParameters:
    """Create the shared timeout and bounded-retry policy for model Activities."""
    return ModelActivityParameters(
        schedule_to_close_timeout=timedelta(
            seconds=settings.temporal_model_schedule_to_close_seconds
        ),
        start_to_close_timeout=timedelta(seconds=settings.temporal_model_start_to_close_seconds),
        heartbeat_timeout=timedelta(seconds=settings.temporal_model_heartbeat_seconds),
        streaming_topic=settings.temporal_streaming_topic,
        retry_policy=RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=settings.temporal_model_max_attempts,
        ),
    )


def create_openai_agents_plugin(
    settings: Settings, *, model_provider: ModelProvider | None = None
) -> OpenAIAgentsPlugin:
    """Create the identically configured plugin used by workers and clients."""
    return OpenAIAgentsPlugin(
        model_params=create_model_activity_parameters(settings),
        model_provider=model_provider,
    )
