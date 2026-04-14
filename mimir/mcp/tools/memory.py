from datetime import UTC, datetime

from mimir.logger import logger
from mimir.mcp.config import mcp_config
from mimir.mcp.app import mcp
from mimir.mcp.decorators import require_approval


@mcp.tool()
@require_approval
async def append_to_semantic_memory(text: str) -> dict[str, str]:
    """Append text to the semantic memory file with a yyyy-mm-dd hh:mm:ss timestamp."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n|{timestamp}| {text}"

    with open(mcp_config.semantic_memory_path, "a", encoding="utf-8") as f:
        f.write(entry)

    logger.info("append_to_semantic_memory: appended to memory")
    return {"message": "Successfully appended to semantic memory."}
