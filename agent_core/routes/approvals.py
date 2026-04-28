from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.approval import store
from shared.models import ActionStatus
from shared.db import get_db
from shared.logger import logger
from shared.schemas import (
    PendingActionCreate,
    PendingActionPatch,
    PendingActionResponse,
)

router = APIRouter()


class ApprovalReactionBody(BaseModel):
    message_ts: str
    reaction: str
    user_id: str


class ApprovalReplyBody(BaseModel):
    thread_ts: str
    text: str
    user_id: str


@router.get("/approvals", response_model=list[PendingActionResponse])
async def list_approvals(
    message_ts: str | None = None,
    thread_ts: str | None = None,
    timed_out: bool = False,
    session: AsyncSession = Depends(get_db),
) -> list[PendingActionResponse]:
    actions = await store.get_all(
        session, message_ts=message_ts, thread_ts=thread_ts, timed_out=timed_out
    )
    return [PendingActionResponse.model_validate(a) for a in actions]


@router.get("/approvals/{action_id}", response_model=PendingActionResponse)
async def get_approval(
    action_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> PendingActionResponse:
    action = await store.get_by_id(session, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return PendingActionResponse.model_validate(action)


@router.post("/approvals", response_model=PendingActionResponse, status_code=201)
async def create_approval(
    body: PendingActionCreate,
    session: AsyncSession = Depends(get_db),
) -> PendingActionResponse:
    action = await store.create(
        session,
        payload=body.payload,
        channel_id=body.channel_id,
        message_ts=body.message_ts,
        triggered_by=body.triggered_by,
        timeout_at=body.timeout_at,
        parent_id=body.parent_id,
    )
    return PendingActionResponse.model_validate(action)


@router.patch("/approvals/{action_id}", response_model=PendingActionResponse)
async def patch_approval(
    action_id: UUID,
    body: PendingActionPatch,
    session: AsyncSession = Depends(get_db),
) -> PendingActionResponse:
    try:
        status = ActionStatus(body.status)
    except ValueError:
        logger.warning(
            "invalid_action_status_patch", status=body.status, action_id=str(action_id)
        )
        raise HTTPException(status_code=422, detail=f"Unknown status: {body.status!r}")

    action = await store.get_by_id(session, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    await store.set_status(session, action_id, status)
    await session.refresh(action)
    return PendingActionResponse.model_validate(action)


@router.post("/approvals/reaction")
async def handle_approval_reaction(
    body: ApprovalReactionBody,
    session: AsyncSession = Depends(get_db),
) -> dict:
    from agent_core.agent.approval import manager

    await manager.handle_reaction(session, body.reaction, body.message_ts, body.user_id)
    return {}


@router.post("/approvals/reply")
async def handle_approval_reply(
    body: ApprovalReplyBody,
    session: AsyncSession = Depends(get_db),
) -> dict:
    from agent_core.agent.approval import manager

    consumed, reply = await manager.handle_thread_reply(
        session,
        thread_ts=body.thread_ts,
        text=body.text,
        user_id=body.user_id,
    )
    return {"consumed": consumed, "reply": reply}
