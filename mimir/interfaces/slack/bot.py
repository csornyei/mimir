import asyncio
import httpx
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from mimir.config import config

from mimir.models import ChatRequest, ChatResponse

app = AsyncApp(token=config.slack_bot_token)
_agent_url = "http://127.0.0.1:8000"
_bot_user_id: str | None = None


async def _get_bot_user_id(client) -> str:
    global _bot_user_id
    if _bot_user_id is None:
        auth_response = await client.auth_test()
        _bot_user_id = auth_response["user_id"]
    return _bot_user_id


def _conversation_id(event: dict) -> str:
    """
    For DMs, use the channel ID as conversation ID.
    Channel threads: use the thread_ts as conversation ID if available, otherwise fallback to channel ID.
    """
    if event.get("channel_type") == "im":
        return event["channel"]
    return event.get("thread_ts") or event["ts"]


async def _send_to_agent(channel_id: str, user_id: str, text: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        payload = ChatRequest(
            conversation_id=channel_id,
            message=text,
            user_id=user_id,
        )

        response = await client.post(
            f"{_agent_url}/api/chat",
            json=payload.model_dump(),
        )
        response.raise_for_status()

        chat_response = ChatResponse.model_validate(response.json())

        return chat_response.response


@app.event("app_mention")
async def handle_mention(event: dict, say, client):
    bot_id = await _get_bot_user_id(client)
    text = event.get("text", "").replace(f"<@{bot_id}>", "").strip()

    reply = await _send_to_agent(_conversation_id(event), event["user"], text)
    await say(text=reply, thread_ts=event.get("thread_ts") or event["ts"])


@app.event("message")
async def handle_message(event: dict, say, client):
    channel_type = event.get("channel_type")
    subtype = event.get("subtype")
    thread_ts = event.get("thread_ts")

    # ignore edits, deletions, bot messages etc.
    if subtype or event.get("bot_id"):
        return

    # DM: always respond
    if channel_type == "im":
        reply = await _send_to_agent(
            _conversation_id(event), event["user"], event.get("text", "")
        )
        await say(text=reply)
        return

    # Channel Threads: only respond if Mimir is already in the thread
    if channel_type in ("channel", "group") and thread_ts:
        history = await client.conversations_replies(
            channel=event["channel"],
            ts=thread_ts,
        )
        bot_id = await _get_bot_user_id(client)

        already_in_thread = any(
            msg.get("user") == bot_id or msg.get("bot_id") == bot_id
            for msg in history.get("messages", [])
            if msg.get("ts") != event["ts"]  # ignore the current message
        )

        if already_in_thread:
            reply = await _send_to_agent(
                _conversation_id(event), event["user"], event.get("text", "")
            )
            await say(text=reply, thread_ts=thread_ts)
        return


async def start():
    handler = AsyncSocketModeHandler(app, config.slack_app_token)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(start())
