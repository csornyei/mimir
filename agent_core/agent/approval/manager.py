from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.approval import executor, store
from agent_core.ws import registry as ws_registry
from shared.models import ActionStatus, PendingActionModel
from agent_core.agent import client as agent_client
from agent_core.config import agent_config
from shared.logger import logger
from shared.const import APPROVE_EMOJI_NAMES, REJECT_EMOJI_NAMES

_tracer = trace.get_tracer("mimir.agent.approval.manager")

_slack = AsyncWebClient(token=agent_config.slack_bot_token)


def _get_web_conversation_id(action: PendingActionModel) -> str | None:
    return action.payload.get("web_conversation_id")


def _format_approval_message(payload: dict) -> str:
    description = payload.get("description", "perform an action")
    return (
        f"I'd like to {description}.\n\n"
        "✅ to go ahead · ❌ to cancel · or reply here to discuss"
    )


async def request_approval(
    session: AsyncSession,
    *,
    payload: dict,
    triggered_by: str,
    parent_id: UUID | None = None,
) -> PendingActionModel:
    """Post an approval request to Slack and create a DB record."""
    with _tracer.start_as_current_span("approval.request") as span:
        tool_name = payload.get("tool_name", "unknown")
        span.set_attribute("approval.tool_name", tool_name)
        span.set_attribute("approval.triggered_by", triggered_by)

        text = _format_approval_message(payload)

        # Slack notification is best-effort — failures don't block the PWA approval flow
        try:
            slack_response = await _slack.chat_postMessage(
                channel=agent_config.slack_dm_channel_id,
                text=text,
            )
            message_ts: str = slack_response["ts"]
        except Exception as slack_err:
            logger.warning(
                "approval_slack_notification_failed",
                error=str(slack_err),
                error_type=type(slack_err).__name__,
                tool_name=tool_name,
            )
            message_ts = f"web_{uuid4()}"

        timeout_at = (
            datetime.now(UTC) + timedelta(minutes=agent_config.approval_timeout_minutes)
            if agent_config.approval_timeout_minutes > 0
            else None
        )

        action = await store.create(
            session,
            payload=payload,
            channel_id=agent_config.slack_dm_channel_id,
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
        logger.debug(
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
        logger.debug("approval_unknown_emoji", emoji=emoji, action_id=str(action.id))


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
        sent = web_conv_id and await ws_registry.send(
            web_conv_id,
            {
                "type": "approval_result",
                "action_id": str(action.id),
                "status": "completed",
                "result": str(result),
            },
        )
        if not sent:
            try:
                await _slack.chat_postMessage(
                    channel=action.channel_id,
                    thread_ts=action.message_ts,
                    text=f"✅ Done. {result}",
                )
            except Exception as slack_err:
                logger.warning(
                    "approval_slack_result_post_failed",
                    action_id=str(action.id),
                    error=str(slack_err),
                    error_type=type(slack_err).__name__,
                )
    except Exception as e:
        await store.set_status(
            session, action.id, ActionStatus.rejected, resolved_at=datetime.now(UTC)
        )
        sent = web_conv_id and await ws_registry.send(
            web_conv_id,
            {
                "type": "approval_result",
                "action_id": str(action.id),
                "status": "failed",
                "error": str(e),
            },
        )
        if not sent:
            try:
                await _slack.chat_postMessage(
                    channel=action.channel_id,
                    thread_ts=action.message_ts,
                    text=f"⚠️ Execution failed: {e!s}",
                )
            except Exception as slack_err:
                logger.warning(
                    "approval_slack_failure_post_failed",
                    action_id=str(action.id),
                    error=str(slack_err),
                    error_type=type(slack_err).__name__,
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
            sent = web_conv_id and await ws_registry.send(
                web_conv_id,
                {
                    "type": "response",
                    "content": llm_reply,
                    "conversation_id": web_conv_id,
                },
            )
            if not sent:
                try:
                    await _slack.chat_postMessage(
                        channel=action.channel_id,
                        thread_ts=action.message_ts,
                        text=llm_reply,
                    )
                except Exception as slack_err:
                    logger.warning(
                        "approval_slack_reinvoke_post_failed",
                        action_id=str(action.id),
                        error=str(slack_err),
                        error_type=type(slack_err).__name__,
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
    sent = web_conv_id and await ws_registry.send(
        web_conv_id,
        {"type": "approval_result", "action_id": str(action.id), "status": "rejected"},
    )
    if not sent:
        description = action.payload.get("description", "the action")
        try:
            await _slack.chat_postMessage(
                channel=action.channel_id,
                thread_ts=action.message_ts,
                text=f"❌ Cancelled. {description}",
            )
        except Exception as slack_err:
            logger.warning(
                "approval_slack_reject_post_failed",
                action_id=str(action.id),
                error=str(slack_err),
                error_type=type(slack_err).__name__,
            )
    logger.info("approval_rejected", action_id=str(action.id))


async def handle_thread_reply(
    session: AsyncSession,
    thread_ts: str,
    text: str,
    user_id: str,
) -> tuple[bool, str | None]:
    """Handle a user reply in an approval thread.

    Returns (consumed, reply_text). consumed=True if this thread belongs to an
    approval; reply_text is the LLM response to post, or None if nothing to post.
    """
    action = await store.get_by_thread_ts(session, thread_ts)
    if action is None:
        return False, None

    terminal = {ActionStatus.completed, ActionStatus.rejected}
    if action.status in terminal:
        return False, None

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
        return True, reply
    except Exception as e:
        logger.error(
            "approval_discuss_failed",
            action_id=str(action.id),
            tool_name=action.payload.get("tool_name", "unknown"),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return True, "Sorry, something went wrong while processing your reply."


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
        sent = web_conv_id and await ws_registry.send(
            web_conv_id,
            {
                "type": "approval_result",
                "action_id": str(action.id),
                "status": "timeout",
            },
        )
        if not sent:
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
                    tool_name=action.payload.get("tool_name", "unknown"),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
    if actions:
        logger.debug("approval_timeouts_processed", count=len(actions))
