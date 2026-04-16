from mimir.logger import logger
from mimir.db import initialize_db
from mimir.mcp.app import mcp
from mimir.mcp.config import mcp_config

# Side-effect imports — the @mcp.tool() decorators in each module register the
# tools with the mcp instance when the module is first imported.
import mimir.mcp.tools.kubernetes  # noqa: F401
import mimir.mcp.tools.memory  # noqa: F401
import mimir.mcp.tools.search  # noqa: F401


if __name__ == "__main__":
    try:
        initialize_db(mcp_config.database_url)
        logger.info("Starting MCP server...")
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user.")
        exit(0)
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
