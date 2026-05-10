from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.models import RssDigestEntry
from shared.schemas import DigestArticle, DigestFeedbackRequest, DigestRun

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


@router.get("/history", response_model=list[DigestArticle], deprecated=True)
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


@router.get("/runs", response_model=list[DigestRun])
async def get_digest_runs(db: AsyncSession = Depends(get_db)) -> list[DigestRun]:
    """Return distinct digest runs with article counts, newest first."""
    result = await db.execute(
        select(
            RssDigestEntry.digest_run_at,
            RssDigestEntry.window,
            func.count(RssDigestEntry.id).label("article_count"),
        )
        .group_by(RssDigestEntry.digest_run_at, RssDigestEntry.window)
        .order_by(desc(RssDigestEntry.digest_run_at))
    )
    return [
        DigestRun(
            run_at=row.digest_run_at, window=row.window, article_count=row.article_count
        )
        for row in result.all()
    ]


@router.get("/run", response_model=list[DigestArticle])
async def get_digest_run(
    run_at: datetime,
    db: AsyncSession = Depends(get_db),
) -> list[DigestArticle]:
    """Return all articles for a specific digest run timestamp."""
    result = await db.execute(
        select(RssDigestEntry)
        .where(RssDigestEntry.digest_run_at == run_at)
        .order_by(RssDigestEntry.id.asc())
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
