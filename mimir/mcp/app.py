from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from mimir.db import initialize_db, dispose_db
from mimir.mcp.config import mcp_config


@asynccontextmanager
async def _lifespan(server: FastMCP):
    initialize_db(mcp_config.database_url)
    yield
    await dispose_db()


mcp = FastMCP("mimir", host="0.0.0.0", port=8010, lifespan=_lifespan)
