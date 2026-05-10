from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.models import ConversationModel, MessageModel
from shared.schemas import BriefDetail, BriefSummary, MessageResponse

router = APIRouter(prefix="/brief", tags=["brief"])


def _conversation_to_summary(conv: ConversationModel) -> BriefSummary:
    date = conv.id.split("|", 1)[1] if "|" in conv.id else conv.id
    return BriefSummary(id=conv.id, date=date, created_at=conv.created_at)


async def _conversation_to_detail(
    conv: ConversationModel, db: AsyncSession
) -> BriefDetail:
    date = conv.id.split("|", 1)[1] if "|" in conv.id else conv.id
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conv.id)
        .order_by(MessageModel.timestamp.asc())
    )
    messages = [
        MessageResponse(id=m.id, role=m.role, content=m.content, timestamp=m.timestamp)
        for m in result.scalars().all()
    ]
    return BriefDetail(
        id=conv.id, date=date, created_at=conv.created_at, messages=messages
    )


@router.get("", response_model=list[BriefSummary])
async def list_briefs(db: AsyncSession = Depends(get_db)) -> list[BriefSummary]:
    """List all morning brief conversations, newest first."""
    result = await db.execute(
        select(ConversationModel)
        .where(ConversationModel.id.like("morning|%"))
        .order_by(desc(ConversationModel.created_at))
    )
    return [_conversation_to_summary(conv) for conv in result.scalars().all()]


@router.get("/latest", response_model=BriefDetail)
async def get_latest_brief(db: AsyncSession = Depends(get_db)) -> BriefDetail:
    """Return the most recent morning brief with messages."""
    result = await db.execute(
        select(ConversationModel)
        .where(ConversationModel.id.like("morning|%"))
        .order_by(desc(ConversationModel.created_at))
        .limit(1)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="No morning brief found")
    return await _conversation_to_detail(conv, db)


@router.get("/{date}", response_model=BriefDetail)
async def get_brief_by_date(
    date: str, db: AsyncSession = Depends(get_db)
) -> BriefDetail:
    """Return the morning brief for a specific date (YYYY-MM-DD)."""
    conv = await db.get(ConversationModel, f"morning|{date}")
    if conv is None:
        raise HTTPException(
            status_code=404, detail="Morning brief not found for this date"
        )
    return await _conversation_to_detail(conv, db)
