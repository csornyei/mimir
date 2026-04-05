import hashlib
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.llm.client import llm_client
from mimir.logger import logger
from mimir.rag.models import DocumentChunk
from mimir.rag.sources import markdown, pdf


def _sha256(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes())
    return h.hexdigest()


def _parse_metadata(meta: dict) -> dict:
    # Make sure all metadata is JSON-serializable, converting dates to ISO format, removing None values, etc.
    parsed = {}
    for key, value in meta.items():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, bool)):
            parsed[key] = value
        elif hasattr(value, "isoformat"):
            parsed[key] = value.isoformat()
        else:
            parsed[key] = str(value)
    return parsed


async def ingest_file(path: Path, session: AsyncSession) -> int:
    """
    Ingest a single file into the document_chunks table.

    Idempotent: if an existing chunk for this source_path already carries the
    same content_hash the file is unchanged and 0 is returned immediately.

    Returns the number of chunks inserted.
    """
    suffix = path.suffix.lower()
    if suffix not in {".md", ".pdf"}:
        raise ValueError(f"Unsupported file type: {suffix}")

    source_path = str(path)
    content_hash = _sha256(path)

    # Idempotency check — any existing chunk for this file carries the file hash
    existing = await session.execute(
        select(DocumentChunk.content_hash)
        .where(DocumentChunk.source_path == source_path)
        .limit(1)
    )
    row = existing.scalar_one_or_none()
    if row == content_hash:
        logger.info("File unchanged, skipping ingestion", path=source_path)
        return 0

    # Remove stale chunks before re-ingesting
    if row is not None:
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.source_path == source_path)
        )
        logger.info("Deleted stale chunks", path=source_path)

    # Chunk the file
    if suffix == ".md":
        raw_chunks = markdown.chunk(
            path.read_text(encoding="utf-8"), file_name=path.name
        )
        source_type = "markdown"
    else:
        raw_chunks = pdf.chunk(path, file_name=path.name)
        source_type = "pdf"

    if not raw_chunks:
        logger.warning("No chunks produced", path=source_path)
        return 0

    # Embed all chunks in a single batch call, offloaded to a thread
    # to avoid blocking the event loop during model inference
    texts = [text for text, _ in raw_chunks]
    embeddings = await llm_client.embed_batch(texts)

    for index, ((text, meta), embedding) in enumerate(zip(raw_chunks, embeddings)):
        session.add(
            DocumentChunk(
                content=text,
                embedding=embedding,
                source_path=source_path,
                source_type=source_type,
                chunk_index=index,
                content_hash=content_hash,
                metadata_=_parse_metadata(meta),
            )
        )
    inserted = len(raw_chunks)

    logger.info(
        "Ingested file", path=source_path, chunks=inserted, source_type=source_type
    )
    return inserted
