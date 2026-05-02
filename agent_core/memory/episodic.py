from datetime import datetime, UTC

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.llm.client import llm_client
from agent_core.llm.embedding import embedding_model
from agent_core.llm.prompt import format_episodic_context
from shared.models import ConversationModel, EpisodicMemoryModel, MessageModel
from agent_core.config import agent_config
from shared.logger import logger

_tracer = trace.get_tracer("mimir.memory.episodic")

_CONSOLIDATION_MIN_MESSAGES = 5
_RETRIEVAL_THRESHOLD = 0.6


class EpisodicMemory:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def consolidate(self, thread_id: str) -> bool:
        conv = await self._session.get(ConversationModel, thread_id)
        if not conv:
            return False

        if conv.consolidated_at is None:
            stmt = (
                select(MessageModel)
                .where(MessageModel.conversation_id == thread_id)
                .order_by(MessageModel.timestamp)
            )
        else:
            stmt = (
                select(MessageModel)
                .where(
                    MessageModel.conversation_id == thread_id,
                    MessageModel.timestamp > conv.consolidated_at,
                )
                .order_by(MessageModel.timestamp)
            )

        messages = (await self._session.scalars(stmt)).all()

        if conv.consolidated_at is None and len(messages) < _CONSOLIDATION_MIN_MESSAGES:
            return False
        if (
            conv.consolidated_at is not None
            and len(messages) < agent_config.episodic_new_messages_threshold
        ):
            return False

        prior_summary: str | None = None
        if conv.consolidated_at is not None:
            prior_row = await self._session.scalar(
                select(EpisodicMemoryModel)
                .where(EpisodicMemoryModel.thread_id == thread_id)
                .order_by(EpisodicMemoryModel.created_at.desc())
                .limit(1)
            )
            if prior_row:
                prior_summary = prior_row.summary

        transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in messages)

        if prior_summary:
            prompt = (
                f"Previous summary of this conversation:\n{prior_summary}\n\n"
                f"New messages since the last summary:\n{transcript}\n\n"
                "Produce an updated 2-3 sentence summary incorporating both the previous summary "
                "and the new messages. Focus on facts, decisions, topics, and context useful for "
                "future recall. Be specific — include names, project names, conclusions."
            )
        else:
            prompt = (
                "Summarise this conversation in 2-3 sentences. "
                "Focus on facts, decisions, topics discussed, and context "
                "that would be useful to recall in a future conversation. "
                "Be specific — include names, project names, conclusions.\n\n"
                f"{transcript}"
            )

        result = await llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        summary = result["content"].strip()

        embedding = await embedding_model.embed_document([summary])

        self._session.add(
            EpisodicMemoryModel(
                summary=summary,
                embedding=embedding,
                thread_id=thread_id,
                started_at=conv.created_at,
                ended_at=conv.last_active,
            )
        )

        conv.consolidated_at = datetime.now(UTC)
        conv.consolidation_retries = 0

        await self._session.commit()
        return True

    async def retrieve(self, query: str, k: int = 3) -> list[dict]:
        try:
            query_embedding = await embedding_model.embed_query(query)

            score_expr = (
                1 - EpisodicMemoryModel.embedding.cosine_distance(query_embedding)
            ).label("score")

            result = await self._session.execute(
                select(
                    EpisodicMemoryModel.summary,
                    EpisodicMemoryModel.started_at,
                    EpisodicMemoryModel.ended_at,
                    score_expr,
                )
                .where(
                    (1 - EpisodicMemoryModel.embedding.cosine_distance(query_embedding))
                    > _RETRIEVAL_THRESHOLD
                )
                .order_by(
                    EpisodicMemoryModel.embedding.cosine_distance(query_embedding)
                )
                .limit(k)
            )

            return [
                {
                    "summary": row.summary,
                    "started_at": row.started_at,
                    "ended_at": row.ended_at,
                    "score": row.score,
                }
                for row in result
            ]
        except Exception as e:
            logger.error(
                "episodic_retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise e

    async def retrieve_formatted(self, query: str, k: int) -> str:
        """Retrieve episodic memories and format for prompt insertion."""
        with _tracer.start_as_current_span("episodic.retrieve_formatted") as span:
            try:
                memories = await self.retrieve(query, k=k)
                span.set_attribute("episodic.memories_found", len(memories))
                logger.debug("episodic_retrieval", count=len(memories))
                return format_episodic_context(memories)
            except Exception as e:
                logger.error(
                    "episodic_retrieval_formatted_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    query_length=len(query),
                    exc_info=True,
                )
                span.set_status(StatusCode.ERROR, str(e))
                return ""
