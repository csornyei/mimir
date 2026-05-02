from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.llm.prompt import token_estimate
from agent_core.rag.retrieval import retrieve
from shared.logger import logger

_tracer = trace.get_tracer("mimir.rag.context")


async def retrieve_rag_context(
    query: str,
    db: AsyncSession,
    max_tokens: int,
) -> tuple[str, int]:
    """Retrieve, budget, and format RAG chunks. Returns (context_string, chunks_used)."""
    with _tracer.start_as_current_span("rag.context") as span:
        try:
            raw = await retrieve(query, db)
            raw_sorted = sorted(raw, key=lambda r: r[1].get("score", 0), reverse=True)

            sections: list[str] = []
            tokens_used = 0
            for content, metadata in raw_sorted:
                chunk_tokens = token_estimate(content)
                if tokens_used + chunk_tokens > max_tokens:
                    logger.warning(
                        "rag_chunk_dropped",
                        score="N/A"
                        if metadata.get("score") is None
                        else round(metadata.get("score", 0), 4),
                        reason="rag_budget_exceeded",
                    )
                    continue
                logger.debug("rag_chunk_retrieved", **metadata)
                source = metadata.get("file_name", "")
                header = metadata.get("header", "")
                page = metadata.get("page", "")
                label = f"{source} {header} {f'(page {page})' if page else ''}".strip()
                sections.append(f"{label}\n{content}")
                tokens_used += chunk_tokens

            chunks_used = len(sections)
            span.set_attribute("rag.chunks_found", chunks_used)
            span.set_attribute("rag.tokens_used", tokens_used)
            return "\n\n---\n\n".join(sections), chunks_used

        except Exception as e:
            logger.error(
                "rag_retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                query_length=len(query),
                exc_info=True,
            )
            span.set_status(StatusCode.ERROR, str(e))
            return "Error while retrieving relevant information.", 0
