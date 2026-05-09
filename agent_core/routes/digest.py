from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.models import RssDigestEntry
from shared.schemas import DigestArticle, DigestFeedbackRequest

router = APIRouter(prefix="/digest", tags=["digest"])


@router.get("/latest", response_model=list[DigestArticle])
async def get_latest_digest(db: AsyncSession = Depends(get_db)) -> list[DigestArticle]:
    """Return all articles from the most recent digest run."""
    latest_run = await db.execute(
        select(RssDigestEntry.digest_run_at)
        .order_by(desc(RssDigestEntry.digest_run_at))
        .limit(1)
    )
    run_at = latest_run.scalar_one_or_none()
    if run_at is None:
        return []

    result = await db.execute(
        select(RssDigestEntry)
        .where(RssDigestEntry.digest_run_at == run_at)
        .order_by(RssDigestEntry.id.asc())
    )
    return [DigestArticle.model_validate(row) for row in result.scalars().all()]


@router.get("/history", response_model=list[DigestArticle])
async def get_digest_history(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[DigestArticle]:
    """Return recent digest articles across all runs."""
    result = await db.execute(
        select(RssDigestEntry)
        .order_by(desc(RssDigestEntry.digest_run_at), RssDigestEntry.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return [DigestArticle.model_validate(row) for row in result.scalars().all()]


@router.post("/feedback", status_code=204)
async def post_feedback(
    body: DigestFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Record a thumbs-up / thumbs-down reaction on a digest article."""
    entry = await db.get(RssDigestEntry, body.article_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Article not found")

    entry.reaction = body.rating
    await db.commit()
