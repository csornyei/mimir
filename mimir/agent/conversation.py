from datetime import datetime, UTC

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.models import ConversationModel, MessageModel


class ConversationManager:
    async def get_or_create_conversation(
        self, session: AsyncSession, conversation_id: str
    ) -> ConversationModel:
        conversation = await session.get(ConversationModel, conversation_id)
        if conversation is None:
            conversation = ConversationModel(id=conversation_id)
            session.add(conversation)
            await session.flush()
        return conversation

    async def add_message(
        self, session: AsyncSession, conversation_id: str, role: str, content: str
    ) -> None:
        session.add(
            MessageModel(conversation_id=conversation_id, role=role, content=content)
        )
        await session.execute(
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(last_active=datetime.now(UTC))
        )

    async def window(
        self, session: AsyncSession, conversation_id: str, n: int
    ) -> list[dict]:
        result = await session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.timestamp.desc())
            .limit(n)
        )
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]


conversation_manager = ConversationManager()
