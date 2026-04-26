import asyncio
from pathlib import Path

from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
    DirCreatedEvent,
    DirModifiedEvent,
)
from watchdog.observers import Observer

from mimir.agent.config import agent_config
from mimir.db import get_session
from mimir.logger import logger
from mimir.rag.ingest import ingest_file

_WATCHED_SUFFIXES = {".md", ".pdf"}


class _VaultEventHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _schedule(self, path: str) -> None:
        p = Path(path)
        if p.suffix.lower() not in _WATCHED_SUFFIXES:
            return
        logger.info("vault_file_changed", path=path)
        asyncio.run_coroutine_threadsafe(self._ingest(p), self._loop)

    async def _ingest(self, path: Path) -> None:
        try:
            async with get_session() as session:
                n = await ingest_file(path, session)
                await session.commit()
            logger.info("vault_file_ingestion_complete", path=str(path), chunks=n)
        except Exception as e:
            logger.error("vault_file_ingestion_failed", path=str(path), error=str(e))

    def on_created(self, event: FileCreatedEvent | DirCreatedEvent) -> None:
        if not event.is_directory:
            self._schedule(f"{event.src_path}")

    def on_modified(self, event: FileModifiedEvent | DirModifiedEvent) -> None:
        if not event.is_directory:
            self._schedule(f"{event.src_path}")


class AsyncFileWatcher:
    def __init__(self) -> None:
        self._observer: Observer | None = None  # type: ignore

    async def start(self) -> None:
        vault_path = agent_config.vault_path
        loop = asyncio.get_running_loop()
        handler = _VaultEventHandler(loop)
        self._observer = Observer()
        self._observer.schedule(handler, vault_path, recursive=True)
        self._observer.start()
        logger.info("file_watcher_started", vault_path=vault_path)

    async def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            logger.info("file_watcher_stopped")
