from typing import Any

import httpx

from shared.logger import logger
from mcp_server.config import mcp_config
from mcp_server.decorators import traced_tool


@traced_tool
async def web_search(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Search the web via SearXNG and return results with title, url, and snippet.

    Use this tool when you need current information, facts you're uncertain about,
    or to research a topic from multiple angles. For thorough research, call this
    multiple times with different query phrasings or angles rather than relying on
    a single search. Snippets are brief — if a result looks highly relevant,
    follow up with web_fetch to get the full content.
    """

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
    """Fetch the content of a web page using the web_fetch service.


    Use this when a search result looks relevant but the snippet is too brief
    to be useful, or when you need the actual content of a page rather than
    a summary. Prefer this over guessing at content you can't see.
    """

    logger.debug("web_fetch", url=url)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(mcp_config.web_fetch_url, params={"url": url})
        response.raise_for_status()
        return response.json()
