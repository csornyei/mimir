from functools import wraps
from typing import Sequence

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from mimir.config import shared_config


class _FilterHeadSpanExporter(SpanExporter):
    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        filtered = [s for s in spans if "HEAD" not in s.name]
        if not filtered:
            return SpanExportResult.SUCCESS
        return self._exporter.export(filtered)

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis)


def setup_tracing(service_name: str, service_version: str = "0.1.0") -> None:
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": shared_config.environment,
        }
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            _FilterHeadSpanExporter(
                OTLPSpanExporter(
                    endpoint=shared_config.otel_exporter_otlp_endpoint, insecure=True
                )
            )
        )
    )
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()


_tracer = trace.get_tracer(__name__)


def slack_span(event_type: str):

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with _tracer.start_as_current_span(
                f"slack.{event_type}",
                kind=trace.SpanKind.SERVER,
            ) as span:
                payload = kwargs.get("event") or kwargs.get("message") or {}
                if isinstance(payload, dict):
                    for key, attr in (
                        ("user", "slack.user_id"),
                        ("channel", "slack.channel_id"),
                        ("thread_ts", "slack.thread_ts"),
                        ("ts", "slack.event_ts"),
                    ):
                        if key in payload:
                            span.set_attribute(attr, payload[key])
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def instrument_sqlalchemy(engine) -> None:
    """Instrument a SQLAlchemy engine. Pass the engine explicitly — no global patching."""
    sync_engine = getattr(engine, "sync_engine", engine)
    SQLAlchemyInstrumentor().instrument(engine=sync_engine)
