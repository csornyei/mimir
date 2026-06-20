"""Async HTTP client for the Obsidian File API (base path /v1/files)."""

from __future__ import annotations

import httpx

from shared.logger import logger


class FileApiClient:
    """Thin async wrapper over the four File API endpoints."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    @staticmethod
    def _normalise_path(path: str) -> str:
        return path.removeprefix("vault/")

    async def list_files(self, path: str = "", type: str = "files_all") -> list[str]:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                "/v1/files/", params={"path": path, "type": type}
            )
            response.raise_for_status()
            result: list[str] = response.json()
            return result

    async def read_file(self, path: str) -> str:
        """Return the text content of a vault file. Returns '' if the file doesn't exist."""
        path = self._normalise_path(path)
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                "/v1/files/read", params={"path": path, "content": "text"}
            )
            if response.status_code == 404:
                return ""
            response.raise_for_status()
            lines: list[str] = response.json().get("content", [])
            return "\n".join(lines)

    async def _create_file(self, path: str, lines: list[str]) -> None:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.post(
                "/v1/files/write",
                params={"path": path},
                json={"frontmatter": None, "content": lines},
            )
            response.raise_for_status()

    async def _update_file(self, path: str, lines: list[str]) -> None:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.patch(
                "/v1/files/write",
                params={"path": path, "type": "content"},
                json={"frontmatter": None, "content": lines},
            )
            response.raise_for_status()

    async def save_file(self, path: str, content: str) -> None:
        """Write content to a file, creating it if it doesn't exist."""
        path = self._normalise_path(path)
        lines = content.splitlines()
        try:
            await self._update_file(path, lines)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                await self._create_file(path, lines)
            else:
                logger.error(
                    "file_api_save_failed",
                    path=path,
                    status=exc.response.status_code,
                    body=exc.response.text,
                )
                raise

    async def append_line(self, path: str, line: str) -> None:
        """Append a single line to the end of a file's content."""
        path = self._normalise_path(path)
        current = await self.read_file(path)
        updated = f"{current}\n{line}" if current else line
        await self.save_file(path, updated)


_client: FileApiClient | None = None


def get_file_api_client() -> FileApiClient:
    """Return the singleton FileApiClient, initialising it on first call."""
    global _client
    if _client is None:
        from shared.config import shared_config

        if not shared_config.file_api_url:
            raise RuntimeError(
                "FILE_API_URL is not configured. "
                "Set the FILE_API_URL environment variable to the File API base URL."
            )
        _client = FileApiClient(shared_config.file_api_url)
    return _client
