from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_summarise_feedback_no_data():
    from shared.reactions import summarise_feedback

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("shared.reactions.get_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await summarise_feedback()

    assert "No feedback" in result


@pytest.mark.asyncio
async def test_summarise_feedback_with_mixed_reactions():
    from shared.reactions import summarise_feedback

    pos = MagicMock(reaction="+1", category="Technology", feed_name="Hacker News")
    neg = MagicMock(reaction="-1", category="Business", feed_name="Forbes")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pos, neg]
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("shared.reactions.get_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await summarise_feedback()

    assert "Technology" in result
    assert "Business" in result
    assert "Hacker News" in result
