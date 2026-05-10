from agent_core.ws.sender import WSSender

_registry: dict[str, WSSender] = {}


def register(conversation_id: str, sender: WSSender) -> None:
    _registry[conversation_id] = sender


def unregister(conversation_id: str) -> None:
    _registry.pop(conversation_id, None)


def get(conversation_id: str) -> WSSender | None:
    return _registry.get(conversation_id)


async def send(conversation_id: str, msg: dict) -> bool:
    """Send to a registered sender. Returns True if a sender was found."""
    sender = _registry.get(conversation_id)
    if sender is None:
        return False
    await sender.send(msg)
    return True
