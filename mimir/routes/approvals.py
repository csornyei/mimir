from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.agent.approval import store
from mimir.models import ActionStatus, ActionType
from mimir.db import get_db
from mimir.schemas import PendingActionCreate, PendingActionPatch, PendingActionResponse

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
    try:
        action_type = ActionType(body.action_type)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Unknown action_type: {body.action_type!r}"
        )

    action = await store.create(
        session,
        action_type=action_type,
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
        raise HTTPException(status_code=422, detail=f"Unknown status: {body.status!r}")

    action = await store.get_by_id(session, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    await store.set_status(session, action_id, status)
    await session.refresh(action)
    return PendingActionResponse.model_validate(action)
