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

from opentelemetry import trace

from shared.config import shared_config


def add_trace_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


structlog.configure(
    cache_logger_on_first_use=True,
    wrapper_class=structlog.make_filtering_bound_logger(shared_config.log_level),
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
        JSONRenderer(),
    ],
)


logger = structlog.get_logger(app_name="mimir", service=shared_config.service_name)
