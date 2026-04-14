from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.agent.approval import executor, store
from mimir.models import ActionStatus, PendingActionModel
from mimir.agent import client as agent_client
from mimir.config import config
from mimir.logger import logger
from mimir.const import APPROVE_EMOJI_NAMES, REJECT_EMOJI_NAMES

_slack = AsyncWebClient(token=config.slack_bot_token)


async def request_approval(
    session: AsyncSession,
    *,
    payload: dict,
    triggered_by: str,
    parent_id: UUID | None = None,
) -> PendingActionModel:
    """Post an approval request to Slack and create a DB record.

    Raises if the Slack post fails — no DB record is created in that case.
    """
    from mimir.interfaces.slack.approval import format_approval_message

    text = format_approval_message(payload)

    slack_response = await _slack.chat_postMessage(
        channel=config.slack_dm_channel_id,
        text=text,
    )
    message_ts: str = slack_response["ts"]

    timeout_at = (
        datetime.now(UTC) + timedelta(minutes=config.approval_timeout_minutes)
        if config.approval_timeout_minutes > 0
        else None
    )

    action = await store.create(
        session,
        payload=payload,
        channel_id=config.slack_dm_channel_id,
        message_ts=message_ts,
        triggered_by=triggered_by,
        timeout_at=timeout_at,
        parent_id=parent_id,
    )

    logger.info(
        "approval_requested",
        action_id=str(action.id),
        message_ts=message_ts,
    )
    return action


async def handle_reaction(
    session: AsyncSession,
    emoji: str,
    message_ts: str,
    user_id: str,
) -> None:
    """Process a reaction on an approval message. emoji must already be base-stripped."""

    action = await store.get_by_message_ts(session, message_ts)
    if action is None:
        return

    terminal = {ActionStatus.completed, ActionStatus.rejected}
    if action.status in terminal:
        logger.info(
            "approval_reaction_ignored_terminal",
            action_id=str(action.id),
            status=action.status,
            emoji=emoji,
        )
        return

    if emoji in APPROVE_EMOJI_NAMES:
        await _handle_approve(session, action, user_id)
    elif emoji in REJECT_EMOJI_NAMES:
        await _handle_reject(session, action)
    else:
        logger.info("approval_unknown_emoji", emoji=emoji, action_id=str(action.id))


async def _handle_approve(
    session: AsyncSession, action: PendingActionModel, user_id: str
) -> None:
    await store.set_status(session, action.id, ActionStatus.approved)

    try:
        result = await executor.execute(action)
        await store.set_status(
            session, action.id, ActionStatus.completed, resolved_at=datetime.now(UTC)
        )
        await _slack.chat_postMessage(
            channel=action.channel_id,
            thread_ts=action.message_ts,
            text=f"✅ Done. {result}",
        )
        logger.info("approval_executed", action_id=str(action.id))
    except Exception as e:
        await store.set_status(
            session, action.id, ActionStatus.rejected, resolved_at=datetime.now(UTC)
        )
        await _slack.chat_postMessage(
            channel=action.channel_id,
            thread_ts=action.message_ts,
            text=f"⚠️ Execution failed: {e!s}",
        )
        logger.error("approval_execution_error", action_id=str(action.id), error=str(e))
        return

    if config.approval_reinvoke_llm:
        description = action.payload.get("description", "the action")
        reinvoke_message = f"[Tool result for '{description}'] {result}"
        try:
            llm_reply = await agent_client.send_to_agent(
                conversation_id=f"{action.channel_id}|{action.message_ts}",
                user_id=user_id,
                message=reinvoke_message,
            )
            await _slack.chat_postMessage(
                channel=action.channel_id,
                thread_ts=action.message_ts,
                text=llm_reply,
            )
        except Exception as e:
            logger.error(
                "approval_reinvoke_failed", action_id=str(action.id), error=str(e)
            )


async def _handle_reject(session: AsyncSession, action: PendingActionModel) -> None:
    await store.set_status(
        session, action.id, ActionStatus.rejected, resolved_at=datetime.now(UTC)
    )
    description = action.payload.get("description", "the action")
    await _slack.chat_postMessage(
        channel=action.channel_id,
        thread_ts=action.message_ts,
        text=f"❌ Cancelled. {description}",
    )
    logger.info("approval_rejected", action_id=str(action.id))


async def handle_thread_reply(
    session: AsyncSession,
    thread_ts: str,
    text: str,
    user_id: str,
    say: Any,
) -> bool:
    """Handle a user reply in an approval thread.

    Returns True if the message was consumed (belongs to an approval thread),
    False if no pending action was found for this thread.
    """
    action = await store.get_by_thread_ts(session, thread_ts)
    if action is None:
        return False

    terminal = {ActionStatus.completed, ActionStatus.rejected}
    if action.status in terminal:
        return False

    if action.status == ActionStatus.pending:
        await store.set_discussing(session, action.id, thread_ts)

    description = action.payload.get("description", "the proposed action")
    enriched = f"[Re: proposed action — {description}] {text}"

    try:
        reply = await agent_client.send_to_agent(
            conversation_id=f"{action.channel_id}|{thread_ts}",
            user_id=user_id,
            message=enriched,
        )
        await say(text=reply, thread_ts=thread_ts)
    except Exception as e:
        logger.error(
            "approval_discuss_failed",
            action_id=str(action.id),
            error=str(e),
        )
        await say(
            text="Sorry, something went wrong while processing your reply.",
            thread_ts=thread_ts,
        )

    return True


async def process_timeouts(session: AsyncSession) -> None:
    """Auto-reject all pending/discussing actions whose timeout_at has passed."""
    actions = await store.get_timed_out(session)
    for action in actions:
        await store.set_status(
            session, action.id, ActionStatus.rejected, resolved_at=datetime.now(UTC)
        )
        try:
            await _slack.chat_postMessage(
                channel=action.channel_id,
                thread_ts=action.message_ts,
                text="⏰ Approval request timed out and was automatically cancelled.",
            )
        except Exception as e:
            logger.error(
                "approval_timeout_notify_failed",
                action_id=str(action.id),
                error=str(e),
            )
    if actions:
        logger.info("approval_timeouts_processed", count=len(actions))
