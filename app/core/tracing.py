"""OpenTelemetry tracing for the corrective-RAG graph, scorecard item 4.

Local-first dev, production-shaped deploy, same split as everywhere else in
this repo (Qdrant, Postgres, checkpointer): no OTEL_EXPORTER_OTLP_ENDPOINT
configured means spans print to the console, with zero external services,
still real tracing, not a stub. Set the endpoint to any OTel-compatible
collector (Jaeger, Grafana Tempo, Honeycomb, ...) to export there instead;
same instrumentation code either way.

get_tracer() is the only thing callers need. It lazily sets up the global
TracerProvider on first call. Tests add their own extra span processor
(see tests/test_tracing.py) to inspect spans in-memory without needing a
real backend or touching this module's setup logic.
"""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from app.core.config import settings
from app.core.version import CODE_VERSION

_initialized = False


def get_tracer():
    global _initialized
    if not _initialized:
        resource = Resource.create(
            {"service.name": "enterprise-rag-assistant", "service.version": CODE_VERSION}
        )
        provider = TracerProvider(resource=resource)

        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _initialized = True

    return trace.get_tracer("enterprise-rag-assistant")
