import asyncio
import json

import opentelemetry.context
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from agent_core.ws.handlers.chat import handle_chat
from agent_core.ws.handlers.ping import handle_ping
from agent_core.ws.sender import WSSender
from shared.logger import logger

HANDLERS = {
    "chat": handle_chat,
    "ping": handle_ping,
}


async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    sender = WSSender(websocket)
    await sender.send({"type": "connected"})

    try:
        async for text in websocket.iter_text():
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                await sender.send({"type": "error", "message": "invalid_json"})
                continue

            event_type = data.get("type")
            handler = HANDLERS.get(event_type)

            if handler is None:
                await sender.send(
                    {
                        "type": "error",
                        "request_id": data.get("request_id"),
                        "message": f"unknown_event_type: {event_type!r}",
                    }
                )
                continue

            ctx = opentelemetry.context.get_current()
            asyncio.create_task(_run_handler(handler, sender, data, ctx))

    except WebSocketDisconnect:
        logger.debug("ws_client_disconnected")


async def _run_handler(handler, sender: WSSender, data: dict, ctx) -> None:
    token = opentelemetry.context.attach(ctx)
    try:
        await handler(sender, data)
    except Exception as e:
        logger.error(
            "ws_handler_unhandled_error",
            event_type=data.get("type"),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
    finally:
        opentelemetry.context.detach(token)
