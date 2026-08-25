from __future__ import annotations

import atexit
import os
from typing import Literal, get_args

from .utils import console

__all__ = ("TRACE_BACKENDS", "TraceBackend", "enable_tracing")

TraceBackend = Literal["langfuse", "otlp"]
# piou only derives choices from a bare Literal, not `Literal | None`.
TRACE_BACKENDS: list[TraceBackend] = list(get_args(TraceBackend))


def _missing_extra(backend: TraceBackend) -> SystemExit:
    extra = "langfuse" if backend == "langfuse" else "otel"
    console.print(f"[red]{backend} tracing dependencies not installed.[/red]")
    console.print(f"[dim]Install the {extra} extra: `uv sync --extra {extra}`.[/dim]")
    return SystemExit(1)


def _enable_langfuse() -> None:
    from padwan_llm.langfuse import instrument

    integration = instrument()
    atexit.register(integration.shutdown)
    console.print("[dim]Tracing enabled (Langfuse)[/dim]")


def _enable_otlp() -> None:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from padwan_llm import otel

    resource = Resource.create({"service.name": "padwan-cli"})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    otel.instrument(tracer_provider=tracer_provider, meter_provider=meter_provider)
    atexit.register(meter_provider.shutdown)
    atexit.register(tracer_provider.shutdown)
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    console.print(f"[dim]Tracing enabled (OTLP → {endpoint})[/dim]")


def enable_tracing(backend: TraceBackend) -> None:
    """Instrument padwan-llm clients for this process, exporting to `backend`.

    `langfuse` reads the standard `LANGFUSE_*` env vars; `otlp` uses the
    standard `OTEL_EXPORTER_OTLP_*` env vars. Exporters are flushed at exit.
    """
    try:
        if backend == "langfuse":
            _enable_langfuse()
        else:
            _enable_otlp()
    except ImportError:
        raise _missing_extra(backend)
