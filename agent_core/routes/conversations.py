from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.conversation import conversation_manager
from shared.models import ConversationModel, MessageModel
from shared.db import get_db
from shared.schemas import ConversationDetail, ConversationSummary, MessageResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationSummary, status_code=201)
async def create_conversation(
    db: AsyncSession = Depends(get_db),
) -> ConversationSummary:
    """Create a new conversation with a web-generated ID."""
    conversation_id = f"web|{uuid4()}"
    conversation = await conversation_manager.get_or_create_conversation(
        db, conversation_id
    )
    await db.commit()
    return ConversationSummary(
        id=conversation.id,
        created_at=conversation.created_at,
        last_active=conversation.last_active,
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation and all its messages (cascade)."""
    conversation = await db.get(ConversationModel, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conversation)
    await db.commit()


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    result = await db.execute(
        select(ConversationModel)
        .where(not_(ConversationModel.id.like("morning|%")))
        .order_by(ConversationModel.last_active.desc())
    )
    return result.scalars().all()  # ty: ignore[invalid-return-type]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conversation = await db.get(ConversationModel, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    visible_filter = (
        MessageModel.conversation_id == conversation_id,
        MessageModel.role != "tool_result",
    )

    total_result = await db.execute(select(func.count()).where(*visible_filter))
    total = total_result.scalar_one()

    messages_result = await db.execute(
        select(MessageModel)
        .where(*visible_filter)
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
