"""Bulk ingestion script.

Usage:
    uv run python -m scripts.ingest --path /vault
    uv run python -m scripts.ingest --path /vault --type markdown
    uv run python -m scripts.ingest --path /vault --type pdf
"""

import argparse
from pathlib import Path

from mimir.db import get_session, initialize_db, dispose_db
from mimir.config import shared_config
from mimir.logger import logger
from mimir.rag.ingest import ingest_file

_SUPPORTED = {".md", ".pdf"}
_TYPE_FILTER = {"markdown": ".md", "pdf": ".pdf"}


async def run(root: Path, type_filter: str | None) -> None:
    suffix_filter = _TYPE_FILTER.get(type_filter) if type_filter else None

    files = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in _SUPPORTED
        and (suffix_filter is None or p.suffix.lower() == suffix_filter)
    ]

    if not files:
        logger.warning(
            "bulk_ingestion_no_files_found", path=str(root), filter=type_filter
        )
        return

    logger.info("bulk_ingestion_started", total_files=len(files), path=str(root))

    total_chunks = 0
    async with get_session() as session:
        for file in files:
            try:
                n = await ingest_file(file, session)
                total_chunks += n
            except Exception as e:
                logger.error("bulk_ingestion_file_failed", path=str(file), error=str(e))
        await session.commit()

    logger.info(
        "bulk_ingestion_complete", total_files=len(files), total_chunks=total_chunks
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk ingest files into Mimir RAG index."
    )
    parser.add_argument(
        "--path", required=True, type=Path, help="Root directory to ingest"
    )
    parser.add_argument(
        "--type",
        choices=["markdown", "pdf"],
        default=None,
        help="Restrict to one file type",
    )
    args = parser.parse_args()

    if not args.path.is_dir():
        parser.error(f"--path must be a directory, got: {args.path}")

    await run(args.path, args.type)


if __name__ == "__main__":
    from asyncio import run as asyncio_run

    async def run_ingest():
        initialize_db(shared_config.database_url)
        await main()
        await dispose_db()

    asyncio_run(run_ingest())
