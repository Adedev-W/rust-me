from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from elrag.lib.observability import (
    ObservabilityConfigurationError,
    _read_positive_int,
    _read_sampling_ratio,
    record_error,
)


class ObservabilityConfigurationTest(unittest.TestCase):
    def test_sampling_ratio_accepts_boundaries(self) -> None:
        with patch.dict("os.environ", {"OTEL_TRACE_SAMPLING_RATIO": "0"}):
            self.assertEqual(0.0, _read_sampling_ratio("OTEL_TRACE_SAMPLING_RATIO", 0.1))

        with patch.dict("os.environ", {"OTEL_TRACE_SAMPLING_RATIO": "1"}):
            self.assertEqual(1.0, _read_sampling_ratio("OTEL_TRACE_SAMPLING_RATIO", 0.1))

    def test_sampling_ratio_rejects_invalid_values(self) -> None:
        for value in ("-0.01", "1.01", "invalid"):
            with self.subTest(value=value), patch.dict(
                "os.environ", {"OTEL_TRACE_SAMPLING_RATIO": value}
            ):
                with self.assertRaises(ObservabilityConfigurationError):
                    _read_sampling_ratio("OTEL_TRACE_SAMPLING_RATIO", 0.1)

    def test_metric_export_interval_must_be_positive_integer(self) -> None:
        with patch.dict("os.environ", {"OTEL_METRIC_EXPORT_INTERVAL_MS": "5000"}):
            self.assertEqual(
                5000, _read_positive_int("OTEL_METRIC_EXPORT_INTERVAL_MS", 60000)
            )

        for value in ("0", "-1", "5.5", "invalid"):
            with self.subTest(value=value), patch.dict(
                "os.environ", {"OTEL_METRIC_EXPORT_INTERVAL_MS": value}
            ):
                with self.assertRaises(ObservabilityConfigurationError):
                    _read_positive_int("OTEL_METRIC_EXPORT_INTERVAL_MS", 60000)


class ObservabilityErrorMetricTest(unittest.TestCase):
    def test_database_and_json_errors_use_separate_counters(self) -> None:
        database_counter = SimpleNamespace(add=Mock())
        json_counter = SimpleNamespace(add=Mock())
        metrics = SimpleNamespace(
            database_error_count=database_counter,
            json_error_count=json_counter,
        )

        with patch("elrag.lib.observability._state.metrics", metrics):
            record_error(
                layer="database",
                code="database_unavailable",
                route="/vision/vision",
                status_code=503,
                operation="read",
            )
            record_error(
                layer="json",
                code="validation_error",
                route="/agent/run",
                status_code=422,
            )

        database_counter.add.assert_called_once()
        json_counter.add.assert_called_once()
        self.assertEqual(
            "database_unavailable",
            database_counter.add.call_args.args[1]["error.code"],
        )
        self.assertEqual(
            "validation_error",
            json_counter.add.call_args.args[1]["error.code"],
        )
