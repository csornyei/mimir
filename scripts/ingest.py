"""Bulk ingestion script.

Usage:
    uv run python scripts/ingest.py --path /vault
    uv run python scripts/ingest.py --path /vault --type markdown
    uv run python scripts/ingest.py --path /vault --type pdf
"""

import argparse
import asyncio
from pathlib import Path

from mimir.db import async_session_factory
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
        logger.warning("No files found", path=str(root), filter=type_filter)
        return

    logger.info("Starting bulk ingestion", total_files=len(files), path=str(root))

    total_chunks = 0
    async with async_session_factory() as session:
        for file in files:
            try:
                n = await ingest_file(file, session)
                total_chunks += n
            except Exception as e:
                logger.error("Failed to ingest file", path=str(file), error=str(e))
        await session.commit()

    logger.info(
        "Bulk ingestion complete", total_files=len(files), total_chunks=total_chunks
    )


def main() -> None:
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

    asyncio.run(run(args.path, args.type))


if __name__ == "__main__":
    main()
