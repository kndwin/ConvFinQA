import os
import unittest
from unittest.mock import patch

from src.platform.config.settings import Settings
from src.platform.observability.bootstrap import _bridge_otel_environment


class ObservabilityBootstrapTests(unittest.TestCase):
    def test_settings_read_otlp_values(self) -> None:
        settings = Settings(
            _env_file=None,
            otel_exporter_otlp_traces_protocol="http/protobuf",
            otel_exporter_otlp_traces_endpoint="http://localhost:4318/v1/traces",
            otel_exporter_otlp_headers="Authorization=Bearer token",
        )

        self.assertIsInstance(settings.otel_exporter_otlp_traces_protocol, str)
        self.assertEqual(settings.otel_exporter_otlp_traces_protocol, "http/protobuf")
        self.assertEqual(
            settings.otel_exporter_otlp_traces_endpoint, "http://localhost:4318/v1/traces"
        )
        self.assertEqual(settings.otel_exporter_otlp_headers, "Authorization=Bearer token")

    def test_bridge_preserves_process_environment(self) -> None:
        settings = Settings(
            _env_file=None,
            otel_exporter_otlp_traces_protocol="http/protobuf",
            otel_exporter_otlp_traces_endpoint="http://localhost:4318/v1/traces",
            otel_exporter_otlp_headers="Authorization=Bearer token",
        )
        variables = {
            "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_EXPORTER_OTLP_HEADERS",
        }

        with patch.dict(os.environ, {name: "process-value" for name in variables}, clear=False):
            _bridge_otel_environment(settings)
            self.assertEqual(os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"], "process-value")
