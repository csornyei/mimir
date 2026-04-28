from collections import Counter

from sqlalchemy import select

from shared.db import get_session
from shared.logger import logger
from shared.models import RssDigestEntry


async def summarise_feedback() -> str:
    async with get_session() as session:
        result = await session.execute(
            select(RssDigestEntry).where(RssDigestEntry.reaction.is_not(None))
        )
        entries = result.scalars().all()

    if not entries:
        return "No feedback recorded yet."

    positive = [e for e in entries if e.reaction == "+1"]
    negative = [e for e in entries if e.reaction == "-1"]

    lines = [
        f"Total feedback: {len(entries)} articles ({len(positive)} liked, {len(negative)} disliked)."
    ]

    pos_cats = Counter(e.category for e in positive if e.category)
    if pos_cats:
        top = ", ".join(f"{cat} (+{n})" for cat, n in pos_cats.most_common(3))
        lines.append(f"Categories you engage with: {top}.")

    neg_cats = Counter(e.category for e in negative if e.category)
    if neg_cats:
        top = ", ".join(f"{cat} (-{n})" for cat, n in neg_cats.most_common(3))
        lines.append(f"Categories you skip: {top}.")

    pos_feeds = Counter(e.feed_name for e in positive if e.feed_name)
    if pos_feeds:
        top = ", ".join(feed for feed, _ in pos_feeds.most_common(3))
        lines.append(f"Sources you prefer: {top}.")

    return " ".join(lines)


async def record_reaction(message_ts: str, reaction: str) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(RssDigestEntry).where(RssDigestEntry.slack_message_ts == message_ts)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            logger.debug("record_reaction_no_match", message_ts=message_ts)
            return
        entry.reaction = reaction
        logger.debug("record_reaction_saved", message_ts=message_ts, reaction=reaction)
