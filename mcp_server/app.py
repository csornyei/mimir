from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from opentelemetry.instrumentation.starlette import StarletteInstrumentor

from shared.db import initialize_db, dispose_db
from shared.logger import logger
from mcp_server.config import mcp_config
from shared.telemetry import setup_tracing

setup_tracing(service_name=mcp_config.service_name)
StarletteInstrumentor().instrument()


@asynccontextmanager
async def _lifespan(server: FastMCP):
    initialize_db(mcp_config.database_url)
    logger.info("mcp_server_started")
    yield
    await dispose_db()
    logger.info("mcp_server_stopped")


mcp = FastMCP("mimir", host="0.0.0.0", port=8010, lifespan=_lifespan)
