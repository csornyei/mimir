from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.approval import store
from shared.models import ActionStatus
from shared.db import get_db
from shared.logger import logger
from shared.schemas import (
    ApproveRequest,
    PendingActionCreate,
    PendingActionPatch,
    PendingActionResponse,
)

router = APIRouter()


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


@router.get("/approvals/{action_id}", response_model=PendingActionResponse)
async def get_approval(
    action_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> PendingActionResponse:
    action = await store.get_by_id(session, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
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


@router.post("/approvals/{action_id}/approve", response_model=PendingActionResponse)
async def approve_approval(
    action_id: UUID,
    body: ApproveRequest,
    session: AsyncSession = Depends(get_db),
) -> PendingActionResponse:
    from agent_core.agent.approval import manager

    action = await store.get_by_id(session, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    terminal = {ActionStatus.completed, ActionStatus.rejected}
    if action.status in terminal:
        raise HTTPException(
            status_code=409, detail=f"Action already in terminal state: {action.status}"
        )

    if body.edited_arguments:
        action.payload = {**action.payload, "arguments": body.edited_arguments}

    try:
        await manager.approve_action(session, action, "web")
    except Exception as e:
        await session.rollback()
        logger.error(
            "approve_action_failed",
            action_id=str(action_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Approval execution failed")
    await session.refresh(action)
    return PendingActionResponse.model_validate(action)


@router.post("/approvals/{action_id}/reject", response_model=PendingActionResponse)
async def reject_approval(
    action_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> PendingActionResponse:
    from agent_core.agent.approval import manager

    action = await store.get_by_id(session, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    terminal = {ActionStatus.completed, ActionStatus.rejected}
    if action.status in terminal:
        raise HTTPException(
            status_code=409, detail=f"Action already in terminal state: {action.status}"
        )

    try:
        await manager.reject_action(session, action)
    except Exception as e:
        await session.rollback()
        logger.error(
            "reject_action_failed",
            action_id=str(action_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Rejection failed")
    await session.refresh(action)
    return PendingActionResponse.model_validate(action)
