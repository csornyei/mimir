from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.llm.client import llm_client
from mimir.models import ConversationModel, EpisodicMemoryModel, MessageModel
from mimir.agent.config import agent_config
from mimir.logger import logger

_CONSOLIDATION_MIN_MESSAGES = 5
_RETRIEVAL_THRESHOLD = 0.6


class EpisodicMemory:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def consolidate(self, thread_id: str) -> bool:
        """
        Summarise a conversation and store as an episodic memory.

        - Fresh path: conversation has never been consolidated — summarise all messages.
        - Re-consolidation path: conversation was consolidated but new messages arrived —
          build an updated summary from the previous summary + new messages.

        Returns True if a new memory was stored, False if skipped.
        Raises on error so the caller can increment consolidation_retries.
        """
        conv = await self._session.get(ConversationModel, thread_id)
        if not conv:
            return False

        if conv.consolidated_at is None:
            # Fresh consolidation — use all messages.
            stmt = (
                select(MessageModel)
                .where(MessageModel.conversation_id == thread_id)
                .order_by(MessageModel.timestamp)
            )
        else:
            # Re-consolidation — only messages since last consolidation.
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

        # Fetch prior summary for re-consolidation context.
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

        embedding = await llm_client.embed(summary)

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
        """
        Return up to k episodic memories most relevant to query.
        Only memories with cosine similarity > _RETRIEVAL_THRESHOLD are returned.
        Each result: {summary, started_at, ended_at, score}.
        """
        try:
            query_embedding = await llm_client.embed(query)

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
            # Log and re-raise so caller can handle (e.g. skip episodic retrieval, increment retries).
            logger.error(
                "episodic_retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise e
