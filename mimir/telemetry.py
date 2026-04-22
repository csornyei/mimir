from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from mimir.config import shared_config


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
            OTLPSpanExporter(
                endpoint=shared_config.otel_exporter_otlp_endpoint, insecure=True
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
