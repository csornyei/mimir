import time

from opentelemetry import trace
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.llm.embedding import embedding_model
from shared.models import DocumentChunk

_tracer = trace.get_tracer("mimir.rag.retrieval")


async def retrieve(
    query: str,
    session: AsyncSession,
    top_k: int = 5,
    threshold: float = 0.6,
    source_type: str | None = None,
) -> list[tuple[str, dict]]:
    """Embed query and return the most similar document chunks."""
    with _tracer.start_as_current_span("rag.retrieve") as span:
        span.set_attribute("rag.query_length", len(query))

        t0 = time.monotonic()
        query_embedding = await embedding_model.embed_query(query)

        stmt = (
            select(
                DocumentChunk.content,
                DocumentChunk.metadata_,
                (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label(
                    "score"
                ),
            )
            .where(
                (1 - DocumentChunk.embedding.cosine_distance(query_embedding))
                >= threshold
            )
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        if source_type is not None:
            stmt = stmt.where(DocumentChunk.source_type == source_type)

        result = await session.execute(stmt)
        rows = [(row.content, {**row.metadata_, "score": row.score}) for row in result]

        retrieval_ms = (time.monotonic() - t0) * 1000
        top_score = max((r[1]["score"] for r in rows), default=0.0)
        span.set_attribute("rag.chunks_found", len(rows))
        span.set_attribute("rag.top_score", round(float(top_score), 4))
        span.set_attribute("rag.retrieval_ms", round(retrieval_ms, 1))

        return rows
