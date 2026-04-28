import hashlib
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.llm.embedding import embedding_model
from shared.logger import logger
from shared.models import DocumentChunk
from agent_core.rag.sources import markdown, pdf


def _sha256(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes())
    return h.hexdigest()


def _parse_metadata(meta: dict) -> dict:
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
    """Ingest a single file into the document_chunks table. Idempotent."""
    suffix = path.suffix.lower()
    if suffix not in {".md", ".pdf"}:
        raise ValueError(f"Unsupported file type: {suffix}")

    source_path = str(path)
    content_hash = _sha256(path)

    existing = await session.execute(
        select(DocumentChunk.content_hash)
        .where(DocumentChunk.source_path == source_path)
        .limit(1)
    )
    row = existing.scalar_one_or_none()
    if row == content_hash:
        logger.debug("vault_file_unchanged", path=source_path)
        return 0

    if row is not None:
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.source_path == source_path)
        )
        logger.debug("vault_file_stale_chunks_deleted", path=source_path)

    if suffix == ".md":
        raw_chunks = markdown.chunk(
            path.read_text(encoding="utf-8"), file_name=path.name
        )
        source_type = "markdown"
    else:
        raw_chunks = pdf.chunk(path, file_name=path.name)
        source_type = "pdf"

    if not raw_chunks:
        logger.warning("vault_file_no_chunks_produced", path=source_path)
        return 0

    texts = [text for text, _ in raw_chunks]
    embeddings = await embedding_model.embed_document(texts)

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
        "vault_file_ingested",
        path=source_path,
        chunks=inserted,
        source_type=source_type,
    )
    return inserted
