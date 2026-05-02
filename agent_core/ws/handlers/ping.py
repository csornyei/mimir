from agent_core.ws.sender import WSSender


async def handle_ping(sender: WSSender, data: dict) -> None:
    await sender.send({"event_type": "pong"})
