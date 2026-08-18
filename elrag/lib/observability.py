from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter 
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

logger = logging.getLogger(__name__)

EXCLUDED_URLS = r"^/docs$|^/redoc$|^/openapi\.json$"


class ObservabilityConfigurationError(RuntimeError):
    """Raised when enabled Google Cloud observability is not configured."""


@dataclass
class _Metrics:
    request_count: Any
    request_duration: Any
    quota_consumed: Any
    quota_rejected: Any
    database_error_count: Any
    json_error_count: Any


@dataclass
class _State:
    configured: bool = False
    enabled: bool = False
    project_id: str | None = None
    error: Exception | None = None
    meter_provider: MeterProvider | None = None
    tracer_provider: TracerProvider | None = None
    metrics: _Metrics | None = None


_state = _State()


def _read_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _read_sampling_ratio(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ObservabilityConfigurationError(
            f"{name} must be a number between 0 and 1"
        ) from exc

    if not 0.0 <= value <= 1.0:
        raise ObservabilityConfigurationError(
            f"{name} must be a number between 0 and 1"
        )
    return value


def _read_positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ObservabilityConfigurationError(f"{name} must be a positive integer") from exc

    if value < 1:
        raise ObservabilityConfigurationError(f"{name} must be a positive integer")
    return value


def _build_metrics() -> _Metrics:
    meter = metrics.get_meter("elrag.observability")
    return _Metrics(
        request_count=meter.create_counter(
            "elrag.api.request.count",
            description="Completed API requests by outcome.",
            unit="{request}",
        ),
        request_duration=meter.create_histogram(
            "elrag.api.request.duration",
            description="API request duration.",
            unit="s",
        ),
        quota_consumed=meter.create_counter(
            "elrag.api.quota.consumed",
            description="Authorized requests that consumed quota.",
            unit="{request}",
        ),
        quota_rejected=meter.create_counter(
            "elrag.api.quota.rejected",
            description="Requests rejected because quota was exhausted.",
            unit="{request}",
        ),
        database_error_count=meter.create_counter(
            "elrag.database.error.count",
            description="Database and database serialization errors.",
            unit="{error}",
        ),
        json_error_count=meter.create_counter(
            "elrag.json.error.count",
            description="Public JSON and API errors.",
            unit="{error}",
        ),
    )


def configure_observability(app: FastAPI) -> None:
    if _state.configured:
        return

    _state.configured = True
    _state.enabled = _read_bool("OTEL_ENABLED", True)
    _state.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

    if _state.enabled and not _state.project_id:
        _state.error = ObservabilityConfigurationError(
            "GOOGLE_CLOUD_PROJECT is required when OTEL_ENABLED is true"
        )
        logger.error("Google Cloud observability is not configured")
    elif _state.enabled:
        try:
            resource = Resource.create(
                {
                    "service.name": os.getenv("OTEL_SERVICE_NAME", "elrag-api"),
                    "service.version": os.getenv("OTEL_SERVICE_VERSION", "unknown"),
                    "deployment.environment": os.getenv(
                        "DEPLOYMENT_ENVIRONMENT", "development"
                    ),
                    "service.instance.id": f"worker-{os.getpid()}",
                }
            )
            tracer_provider = TracerProvider(
                resource=resource,
                sampler=ParentBased(
                    TraceIdRatioBased(
                        _read_sampling_ratio("OTEL_TRACE_SAMPLING_RATIO", 0.1)
                    )
                ),
            )
            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    CloudTraceSpanExporter(project_id=_state.project_id)
                )
            )
            trace.set_tracer_provider(tracer_provider)

            metric_reader = PeriodicExportingMetricReader(
                CloudMonitoringMetricsExporter(project_id=_state.project_id),
                export_interval_millis=_read_positive_int(
                    "OTEL_METRIC_EXPORT_INTERVAL_MS", 60000
                ),
            )
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader],
            )
            metrics.set_meter_provider(meter_provider)
            _state.tracer_provider = tracer_provider
            _state.meter_provider = meter_provider
        except Exception as exc:
            _state.error = exc
            logger.exception("Failed to configure Google Cloud observability")

    _state.metrics = _build_metrics()
    FastAPIInstrumentor.instrument_app(app, excluded_urls=EXCLUDED_URLS)


def validate_observability() -> None:
    if _state.enabled and _state.error is not None:
        raise ObservabilityConfigurationError(
            "Google Cloud observability initialization failed"
        ) from _state.error


def record_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
    authenticated: bool,
    quota_consumed: bool,
) -> None:
    if _state.metrics is None:
        return

    attributes = {
        "http.request.method": method,
        "http.route": route,
        "http.response.status_code": status_code,
        "app.authenticated": authenticated,
    }
    _state.metrics.request_count.add(1, attributes)
    _state.metrics.request_duration.record(duration_seconds, attributes)
    if quota_consumed:
        _state.metrics.quota_consumed.add(1, {"http.route": route})
    if status_code == 429:
        _state.metrics.quota_rejected.add(1, {"http.route": route})


def record_error(
    *,
    layer: str,
    code: str,
    route: str,
    status_code: int,
    operation: str | None = None,
    source: str | None = None,
) -> None:
    """Record a categorized application error without sensitive values."""

    if _state.metrics is None:
        return

    attributes: dict[str, str | int] = {
        "error.code": code,
        "http.route": route,
        "http.response.status_code": status_code,
    }
    if operation:
        attributes["error.operation"] = operation
    if source:
        attributes["error.source"] = source

    if layer == "database":
        _state.metrics.database_error_count.add(1, attributes)
    else:
        _state.metrics.json_error_count.add(1, attributes)


def monotonic() -> float:
    return time.monotonic()


def shutdown_observability() -> None:
    if _state.meter_provider is not None:
        _state.meter_provider.shutdown()
    if _state.tracer_provider is not None:
        _state.tracer_provider.shutdown()
