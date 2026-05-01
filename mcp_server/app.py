from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from opentelemetry.instrumentation.starlette import StarletteInstrumentor

from shared.db import initialize_db, dispose_db
from shared.logger import logger
from mcp_server.config import mcp_config
from shared.telemetry import setup_tracing

setup_tracing(service_name=mcp_config.service_name)

mcp = FastMCP(
    mcp_config.service_name,
    transport_security=TransportSecuritySettings(
        allowed_hosts=mcp_config.allowed_hosts
    ),
)


@asynccontextmanager
async def _lifespan(app):
    async with mcp.session_manager.run():
        initialize_db(mcp_config.database_url)
        logger.info("mcp_server_started")
        yield
        await dispose_db()
        logger.info("mcp_server_stopped")


app = mcp.streamable_http_app()

app.router.lifespan_context = _lifespan

StarletteInstrumentor().instrument_app(app)
