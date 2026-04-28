from datetime import UTC, datetime

from shared.logger import logger
from mcp_server.config import mcp_config
from mcp_server.decorators import write_tool


@write_tool
async def append_to_semantic_memory(text: str) -> dict[str, str]:
    """Append text to the semantic memory file with a yyyy-mm-dd hh:mm:ss timestamp."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n|{timestamp}| {text}"

    with open(mcp_config.semantic_memory_path, "a", encoding="utf-8") as f:
        f.write(entry)

    logger.debug("append_to_semantic_memory: appended to memory")
    return {"message": "Successfully appended to semantic memory."}
