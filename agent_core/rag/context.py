from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.llm.prompt import token_estimate
from agent_core.rag.retrieval import retrieve
from shared.logger import logger

_tracer = trace.get_tracer("mimir.rag.context")


def _source_type(file_name: str) -> str:
    lower = file_name.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    return "markdown"


async def retrieve_rag_context(
    query: str,
    db: AsyncSession,
    max_tokens: int,
) -> tuple[str, int, list[dict]]:
    """Retrieve, budget, and format RAG chunks.

    Returns (context_string, chunks_used, rag_sources) where rag_sources is a list
    of source metadata dicts suitable for the WS ``done`` event.
    """
    with _tracer.start_as_current_span("rag.context") as span:
        try:
            raw = await retrieve(query, db)
            raw_sorted = sorted(raw, key=lambda r: r[1].get("score", 0), reverse=True)

            sections: list[str] = []
            rag_sources: list[dict] = []
            tokens_used = 0

            for idx, (content, metadata) in enumerate(raw_sorted):
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
                file_name = metadata.get("file_name", "")
                header = metadata.get("header", "")
                page = metadata.get("page", "")
                label = (
                    f"{file_name} {header} {f'(page {page})' if page else ''}".strip()
                )
                sections.append(f"{label}\n{content}")
                tokens_used += chunk_tokens

                rag_sources.append(
                    {
                        "source_path": file_name,
                        "source_type": _source_type(file_name),
                        "chunk_index": idx,
                        "similarity_score": float(metadata.get("score", 0.0)),
                        "content_preview": content[:150],
                    }
                )

            chunks_used = len(sections)
            span.set_attribute("rag.chunks_found", chunks_used)
            span.set_attribute("rag.tokens_used", tokens_used)
            return "\n\n---\n\n".join(sections), chunks_used, rag_sources

        except Exception as e:
            logger.error(
                "rag_retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                query_length=len(query),
                exc_info=True,
            )
            span.set_status(StatusCode.ERROR, str(e))
            return "Error while retrieving relevant information.", 0, []
