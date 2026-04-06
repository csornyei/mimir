from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.llm.client import llm_client
from mimir.models import DocumentChunk


async def retrieve(
    query: str,
    session: AsyncSession,
    top_k: int = 5,
    threshold: float = 0.6,
    source_type: str | None = None,
) -> list[tuple[str, dict]]:
    """
    Embed *query* and return the content of the most similar document chunks.

    Only chunks with cosine similarity >= *threshold* are returned.
    Optionally filter by *source_type* ('markdown' or 'pdf').
    """
    query_embedding = await llm_client.embed(query)

    stmt = (
        select(
            DocumentChunk.content,
            DocumentChunk.metadata_,
            (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label(
                "score"
            ),
        )
        .where(
            (1 - DocumentChunk.embedding.cosine_distance(query_embedding)) >= threshold
        )
        .order_by(text("score DESC"))
        .limit(top_k)
    )

    if source_type is not None:
        stmt = stmt.where(DocumentChunk.source_type == source_type)

    result = await session.execute(stmt)
    return [(row.content, {**row.metadata_, "score": row.score}) for row in result]
