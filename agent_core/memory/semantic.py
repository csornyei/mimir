from datetime import datetime

from agent_core.config import agent_config
from shared.file_api import get_file_api_client


class SemanticMemory:
    """Reads and writes the semantic memory file via the File API."""

    def __init__(self, vault_path: str | None = None) -> None:
        self._vault_path: str = (
            vault_path if vault_path is not None else agent_config.semantic_memory_path
        )

    async def read(self) -> str:
        return await get_file_api_client().read_file(self._vault_path)

    async def write(self, content: str) -> None:
        await get_file_api_client().save_file(self._vault_path, content)

    async def append_fact(self, fact: str) -> None:
        """Append a new fact to the memory file under a ## New Facts section."""
        current = await self.read()
        timestamp = datetime.now().strftime("%Y-%m-%d")
        entry = f"\n- ({timestamp}) {fact}"
        if "## New Facts" in current:
            await self.write(current + entry)
        else:
            await self.write(current + f"\n\n## New Facts\n{entry}")
