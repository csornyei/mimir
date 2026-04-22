import os
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


from mimir.config import shared_config



renderer = JSONRenderer() if shared_config.env == "production" else ConsoleRenderer()

structlog.configure(
    cache_logger_on_first_use=True,
    processors=[
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
