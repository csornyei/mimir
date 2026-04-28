from typing import Any

from shared.reactions import record_reaction


async def on_digest_reaction(event: dict[str, Any], client: Any) -> None:
    item = event.get("item", {})
    if item.get("type") != "message":
        return
    raw_reaction: str = event.get("reaction", "")
    reaction = raw_reaction.split("::")[0]
    if reaction not in ("+1", "-1"):
        return
    await record_reaction(item["ts"], reaction)
