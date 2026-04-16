from typing import Any

from mimir.logger import logger

_bot_user_id: str | None = None


async def get_bot_user_id(client: Any) -> str:
    """Resolve and cache the bot's Slack user ID."""
    global _bot_user_id
    if _bot_user_id is None:
        auth_response = await client.auth_test()
        _bot_user_id = auth_response["user_id"]
        logger.debug("resolved_bot_user_id", bot_user_id=_bot_user_id)
    return _bot_user_id
