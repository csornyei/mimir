from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.approval import executor, store
from agent_core.ws import registry as ws_registry
from shared.models import ActionStatus, PendingActionModel
from agent_core.agent import client as agent_client
from agent_core.config import agent_config
from shared.logger import logger

_tracer = trace.get_tracer("mimir.agent.approval.manager")


def _get_web_conversation_id(action: PendingActionModel) -> str | None:
    return action.payload.get("web_conversation_id")


async def request_approval(
    session: AsyncSession,
    *,
    payload: dict,
    triggered_by: str,
    parent_id: UUID | None = None,
) -> PendingActionModel:
    """Create a DB record for an approval request."""
    with _tracer.start_as_current_span("approval.request") as span:
        tool_name = payload.get("tool_name", "unknown")
        span.set_attribute("approval.tool_name", tool_name)
        span.set_attribute("approval.triggered_by", triggered_by)

        message_ts = f"web_{uuid4()}"

        timeout_at = (
            datetime.now(UTC) + timedelta(minutes=agent_config.approval_timeout_minutes)
            if agent_config.approval_timeout_minutes > 0
            else None
        )

        action = await store.create(
            session,
            payload=payload,
            channel_id="web",
            message_ts=message_ts,
            triggered_by=triggered_by,
            timeout_at=timeout_at,
            parent_id=parent_id,
        )

        span.set_attribute("approval.action_id", str(action.id))
        logger.info(
            "approval_requested",
            action_id=str(action.id),
            message_ts=message_ts,
        )
        return action


async def _handle_approve(
    session: AsyncSession, action: PendingActionModel, user_id: str
) -> None:
    await store.set_status(session, action.id, ActionStatus.approved)
    await session.commit()

    web_conv_id = _get_web_conversation_id(action)

    try:
        result = await executor.execute(action)
        if isinstance(result, dict) and "error" in result:
            raise Exception(result["error"])
        logger.info("approval_execution_succeeded", action_id=str(action.id))
        await store.set_status(
            session, action.id, ActionStatus.completed, resolved_at=datetime.now(UTC)
        )
        if web_conv_id:
            await ws_registry.send(
                web_conv_id,
                {
                    "type": "approval_result",
                    "action_id": str(action.id),
                    "status": "completed",
                    "result": str(result),
                },
            )
    except Exception as e:
        await store.set_status(
            session, action.id, ActionStatus.rejected, resolved_at=datetime.now(UTC)
        )
        if web_conv_id:
            await ws_registry.send(
                web_conv_id,
                {
                    "type": "approval_result",
                    "action_id": str(action.id),
                    "status": "failed",
                    "error": str(e),
                },
            )
        logger.error(
            "approval_execution_error",
            action_id=str(action.id),
            error=str(e),
            tool_name=action.payload.get("tool_name", "unknown"),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return

    if agent_config.approval_reinvoke_llm:
        description = action.payload.get("description", "the action")
        reinvoke_message = f"[Tool result for '{description}'] {result}"
        reinvoke_conv_id = web_conv_id or f"{action.channel_id}|{action.message_ts}"
        try:
            llm_reply = await agent_client.send_to_agent(
                conversation_id=reinvoke_conv_id,
                user_id=user_id,
                message=reinvoke_message,
                message_role="tool_result",
            )
            if web_conv_id:
                await ws_registry.send(
                    web_conv_id,
                    {
                        "type": "response",
                        "content": llm_reply,
                        "conversation_id": web_conv_id,
                    },
                )
        except Exception as e:
            logger.error(
                "approval_reinvoke_failed",
                action_id=str(action.id),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )


async def _handle_reject(session: AsyncSession, action: PendingActionModel) -> None:
    with _tracer.start_as_current_span("approval.execute") as span:
        span.set_attribute("approval.action_id", str(action.id))
        span.set_attribute(
            "approval.tool_name", action.payload.get("tool_name", "unknown")
        )
        span.set_attribute("approval.outcome", "rejected")
        span.set_status(StatusCode.ERROR, "approval_rejected_by_user")
    await store.set_status(
        session, action.id, ActionStatus.rejected, resolved_at=datetime.now(UTC)
    )
    web_conv_id = _get_web_conversation_id(action)
    if web_conv_id:
        await ws_registry.send(
            web_conv_id,
            {
                "type": "approval_result",
                "action_id": str(action.id),
                "status": "rejected",
            },
        )
    logger.info("approval_rejected", action_id=str(action.id))


async def approve_action(
    session: AsyncSession, action: PendingActionModel, user_id: str = "web"
) -> None:
    """Approve a pending action and execute it."""
    await _handle_approve(session, action, user_id)


async def reject_action(session: AsyncSession, action: PendingActionModel) -> None:
    """Reject a pending action."""
    await _handle_reject(session, action)


async def process_timeouts(session: AsyncSession) -> None:
    """Auto-reject all pending/discussing actions whose timeout_at has passed."""
    actions = await store.get_timed_out(session)
    for action in actions:
        with _tracer.start_as_current_span("approval.execute") as span:
            span.set_attribute("approval.action_id", str(action.id))
            span.set_attribute(
                "approval.tool_name", action.payload.get("tool_name", "unknown")
            )
            span.set_attribute("approval.outcome", "timeout")
            span.set_status(StatusCode.ERROR, "approval_timed_out")
        await store.set_status(
            session, action.id, ActionStatus.rejected, resolved_at=datetime.now(UTC)
        )
        web_conv_id = _get_web_conversation_id(action)
        if web_conv_id:
            await ws_registry.send(
                web_conv_id,
                {
                    "type": "approval_result",
                    "action_id": str(action.id),
                    "status": "timeout",
                },
            )
    if actions:
        logger.debug("approval_timeouts_processed", count=len(actions))
