import asyncio
from datetime import UTC, datetime

from mimir.agent.mcp_client import fetch_tools_openai_format
from mimir.config import config
from mimir.logger import logger


class ToolSchemaRegistry:
    """Fetch and cache tool schemas from the MCP server."""

    def __init__(self):
        self._schemas: list[dict] | None = None
        self._cache_time: datetime | None = None
        self._fetching: asyncio.Lock = asyncio.Lock()

    async def _fetch_from_mcp(self) -> list[dict]:
        try:
            tools = await fetch_tools_openai_format()
            return tools
        except Exception as e:
            logger.error(
                "failed_to_fetch_tool_schemas",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def get_tools(self, refresh: bool = False) -> list[dict]:
        """Get tool schemas with TTL-based caching.

        Args:
            refresh: Force refresh cache, ignoring TTL

        Returns:
            List of OpenAI-format tool schemas

        Raises:
            Exception if MCP server is unreachable
        """
        now = datetime.now(UTC)

        # Check if cache is still valid
        if not refresh and self._schemas is not None and self._cache_time is not None:
            age = (now - self._cache_time).total_seconds()
            if age < config.mcp_schema_cache_ttl_seconds:
                logger.info("tool_schemas_cached", age_seconds=int(age))
                return self._schemas

        # Fetch with lock to avoid concurrent requests
        async with self._fetching:
            # Double-check after acquiring lock
            if (
                not refresh
                and self._schemas is not None
                and self._cache_time is not None
            ):
                age = (now - self._cache_time).total_seconds()
                if age < config.mcp_schema_cache_ttl_seconds:
                    return self._schemas

            # Fetch from MCP server
            self._schemas = await self._fetch_from_mcp()
            self._cache_time = now

        return self._schemas


# Global registry instance
tool_schema_registry = ToolSchemaRegistry()
