from typing import Any

import httpx

from shared.logger import logger
from mcp_server.config import mcp_config
from mcp_server.decorators import traced_tool


@traced_tool
async def web_search(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Search the web via SearXNG and return results with title, url, and snippet."""
    logger.debug("web_search", query=query, num_results=num_results)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{mcp_config.searxng_url}/search",
            params={"q": query, "format": "json", "number_of_results": num_results},
        )
        response.raise_for_status()
        data = response.json()

    return [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": r.get("content"),
        }
        for r in data.get("results", [])[:num_results]
    ]


@traced_tool
async def web_fetch(url: str) -> dict[str, Any] | None:
    """Fetch the content of a web page using the web_fetch service."""
    logger.debug("web_fetch", url=url)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(mcp_config.web_fetch_url, params={"url": url})
        response.raise_for_status()
        return response.json()
