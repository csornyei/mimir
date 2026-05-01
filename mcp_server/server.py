from shared.logger import logger
from mcp_server.app import mcp

# Side-effect imports — the @mcp.tool() decorators register tools with the mcp instance.
import mcp_server.tools.calendar  # noqa: F401
import mcp_server.tools.kubernetes  # noqa: F401
import mcp_server.tools.memory  # noqa: F401
import mcp_server.tools.search  # noqa: F401
import mcp_server.tools.git  # noqa: F401

if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("mcp_server_stopped_by_user")
        exit(0)
    except Exception as e:
        logger.error(
            "mcp_server_error", error=str(e), error_type=type(e).__name__, exc_info=True
        )
