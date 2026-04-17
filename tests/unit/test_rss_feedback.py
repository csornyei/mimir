from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_summarise_feedback_no_data():
    from mimir.scheduler.rss.feedback import summarise_feedback

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("mimir.scheduler.rss.feedback.get_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await summarise_feedback()

    assert "No feedback" in result


@pytest.mark.asyncio
async def test_summarise_feedback_with_mixed_reactions():
    from mimir.scheduler.rss.feedback import summarise_feedback

    pos = MagicMock(reaction="+1", category="Technology", feed_name="Hacker News")
    neg = MagicMock(reaction="-1", category="Business", feed_name="Forbes")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pos, neg]
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("mimir.scheduler.rss.feedback.get_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await summarise_feedback()

    assert "Technology" in result
    assert "Business" in result
    assert "Hacker News" in result


@pytest.mark.asyncio
async def test_record_reaction_updates_matching_entry():
    from mimir.scheduler.rss.feedback import record_reaction

    mock_entry = MagicMock()
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_entry
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("mimir.scheduler.rss.feedback.get_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await record_reaction("111.222", "+1")

    assert mock_entry.reaction == "+1"


@pytest.mark.asyncio
async def test_record_reaction_no_match_is_noop():
    from mimir.scheduler.rss.feedback import record_reaction

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("mimir.scheduler.rss.feedback.get_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await record_reaction("999.999", "+1")  # should not raise


@pytest.mark.asyncio
async def test_on_digest_reaction_ignores_non_thumbs():
    from mimir.scheduler.rss.feedback import on_digest_reaction

    event = {"reaction": "wave", "item": {"type": "message", "ts": "111.222"}}
    with patch("mimir.scheduler.rss.feedback.record_reaction", new=AsyncMock()) as mock_rec:
        await on_digest_reaction(event, None)
    mock_rec.assert_not_called()


@pytest.mark.asyncio
async def test_on_digest_reaction_ignores_non_message_items():
    from mimir.scheduler.rss.feedback import on_digest_reaction

    event = {"reaction": "+1", "item": {"type": "file", "ts": "111.222"}}
    with patch("mimir.scheduler.rss.feedback.record_reaction", new=AsyncMock()) as mock_rec:
        await on_digest_reaction(event, None)
    mock_rec.assert_not_called()


@pytest.mark.asyncio
async def test_on_digest_reaction_records_thumbs_up():
    from mimir.scheduler.rss.feedback import on_digest_reaction

    event = {"reaction": "+1", "item": {"type": "message", "ts": "111.222"}}
    with patch("mimir.scheduler.rss.feedback.record_reaction", new=AsyncMock()) as mock_rec:
        await on_digest_reaction(event, None)
    mock_rec.assert_awaited_once_with("111.222", "+1")


@pytest.mark.asyncio
async def test_on_digest_reaction_records_thumbs_down():
    from mimir.scheduler.rss.feedback import on_digest_reaction

    event = {"reaction": "-1", "item": {"type": "message", "ts": "111.222"}}
    with patch("mimir.scheduler.rss.feedback.record_reaction", new=AsyncMock()) as mock_rec:
        await on_digest_reaction(event, None)
    mock_rec.assert_awaited_once_with("111.222", "-1")


@pytest.mark.asyncio
async def test_on_digest_reaction_strips_skin_tone():
    from mimir.scheduler.rss.feedback import on_digest_reaction

    event = {"reaction": "+1::skin-tone-3", "item": {"type": "message", "ts": "111.222"}}
    with patch("mimir.scheduler.rss.feedback.record_reaction", new=AsyncMock()) as mock_rec:
        await on_digest_reaction(event, None)
    mock_rec.assert_awaited_once_with("111.222", "+1")
