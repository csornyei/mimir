from datetime import UTC, datetime

from shared.file_api import get_file_api_client
from shared.logger import logger
from mcp_server.decorators import write_tool


@write_tool
async def append_to_semantic_memory(text: str) -> dict[str, str]:
    """Append text to the semantic memory file with a yyyy-mm-dd hh:mm:ss timestamp."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"|{timestamp}| {text}"
    await get_file_api_client().append_line("memory.md", entry)
    logger.debug("append_to_semantic_memory: appended to memory")
    return {"message": "Successfully appended to semantic memory."}
