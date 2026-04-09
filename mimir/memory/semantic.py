from pathlib import Path
from datetime import datetime
from mimir.config import config


class SemanticMemory:
    """
    Reads and writes the memory.md file in the Obsidian vault.
    This file is human-readable and directly editable.
    The agent treats it as the source of truth for facts about the user.
    """

    def __init__(self, path: str | Path | None = None):
        self._path: Path = (
            Path(path) if path is not None else Path(config.semantic_memory_path)
        )

    def read(self) -> str:
        if not self._path.exists():
            return ""

        return self._path.read_text(encoding="utf-8")

    def write(self, content: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._path.write_text(content, encoding="utf-8")

    def append_fact(self, fact: str) -> None:
        """Append a new fact to the memory file under a ## New Facts section."""

        current = self.read()

        timestamp = datetime.now().strftime("%Y-%m-%d")

        entry = f"\n- ({timestamp}) {fact}"
        if "## New Facts" in current:
            self.write(current + entry)
        else:
            self.write(current + f"\n\n## New Facts\n{entry}")
