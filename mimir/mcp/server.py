from mimir.logger import logger
from mimir.mcp.app import mcp

# Side-effect imports — the @mcp.tool() decorators in each module register the
# tools with the mcp instance when the module is first imported.
import mimir.mcp.tools.calendar  # noqa: F401
import mimir.mcp.tools.kubernetes  # noqa: F401
import mimir.mcp.tools.memory  # noqa: F401
import mimir.mcp.tools.search  # noqa: F401


if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("mcp_server_stopped_by_user")
        exit(0)
    except Exception as e:
        logger.error("mcp_server_error", error=str(e))
