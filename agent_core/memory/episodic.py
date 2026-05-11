from datetime import datetime, UTC

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.llm.client import llm_client
from agent_core.llm.params import LLMParams
from agent_core.llm.embedding import embedding_model
from agent_core.prompts import (
    render_episodic_consolidation_initial,
    render_episodic_consolidation_update,
)
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
            prompt = render_episodic_consolidation_update(
                prior_summary=prior_summary, transcript=transcript
            )
        else:
            prompt = render_episodic_consolidation_initial(transcript=transcript)

        result = await llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            params=LLMParams(
                model=agent_config.llm_model,
                temperature=0.3,
                max_tokens=1000,
            ),
        )
        summary = result["content"].strip()

        embedding = await embedding_model.embed_single_document(summary)

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
