from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import ConversationModel, MessageModel
from shared.db import get_db
from shared.schemas import ConversationDetail, ConversationSummary, MessageResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConversationModel).order_by(ConversationModel.last_active.desc())
    )
    return result.scalars().all()


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    conversation = await db.get(ConversationModel, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    total_result = await db.execute(
        select(func.count()).where(MessageModel.conversation_id == conversation_id)
    )
    total = total_result.scalar_one()

    messages_result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.timestamp.asc())
        .limit(limit)
        .offset(offset)
    )
    messages = messages_result.scalars().all()

    return ConversationDetail(
        id=conversation.id,
        created_at=conversation.created_at,
        last_active=conversation.last_active,
        messages=[
            MessageResponse(
                id=m.id, role=m.role, content=m.content, timestamp=m.timestamp
            )
            for m in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
