import structlog
from structlog.processors import (
    TimeStamper,
    add_log_level,
    dict_tracebacks,
    JSONRenderer,
    EventRenamer,
    CallsiteParameterAdder,
    CallsiteParameter,
)
from structlog.dev import ConsoleRenderer

from opentelemetry import trace

from mimir.config import shared_config


def add_trace_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


renderer = JSONRenderer() if shared_config.env == "production" else ConsoleRenderer()

structlog.configure(
    cache_logger_on_first_use=True,
    processors=[
        add_trace_context,
        TimeStamper(fmt="iso"),
        add_log_level,
        dict_tracebacks,
        EventRenamer("message", "_event"),
        CallsiteParameterAdder(
            [
                CallsiteParameter.FILENAME,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
            ]
        ),
        renderer,
    ],
)


logger = structlog.get_logger(app_name="mimir", service=shared_config.service_name)
