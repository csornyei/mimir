from unittest.mock import AsyncMock, patch

import pytest


def _entry(entry_id: int = 1, title: str = "Test Article") -> dict:
    return {
        "id": entry_id,
        "title": title,
        "url": f"https://example.com/{entry_id}",
        "feed_name": "Tech Blog",
        "category": "Technology",
        "summary": "A brief summary of the article.",
    }


def test_build_prompt_includes_entry_title():
    from mimir.scheduler.rss.filter import _build_prompt

    messages = _build_prompt([_entry()], semantic_memory="User likes Python.", feedback_summary="No feedback.", n_picks=5)
    user_content = messages[1]["content"]
    assert "Test Article" in user_content


def test_build_prompt_includes_semantic_memory():
    from mimir.scheduler.rss.filter import _build_prompt

    messages = _build_prompt([_entry()], semantic_memory="User likes Python.", feedback_summary="No feedback.", n_picks=5)
    user_content = messages[1]["content"]
    assert "User likes Python." in user_content


def test_build_prompt_omits_memory_section_when_empty():
    from mimir.scheduler.rss.filter import _build_prompt

    messages = _build_prompt([_entry()], semantic_memory="", feedback_summary="No feedback recorded yet.", n_picks=5)
    user_content = messages[1]["content"]
    assert "About the user" not in user_content


def test_build_prompt_omits_feedback_section_when_no_data():
    from mimir.scheduler.rss.filter import _build_prompt

    messages = _build_prompt([_entry()], semantic_memory="", feedback_summary="No feedback recorded yet.", n_picks=5)
    user_content = messages[1]["content"]
    assert "Past feedback" not in user_content


def test_build_prompt_includes_feedback_when_present():
    from mimir.scheduler.rss.filter import _build_prompt

    messages = _build_prompt([_entry()], semantic_memory="", feedback_summary="You like Python articles.", n_picks=5)
    user_content = messages[1]["content"]
    assert "Past feedback" in user_content
    assert "You like Python articles." in user_content


def test_parse_picks_plain_json():
    from mimir.scheduler.rss.filter import _parse_picks

    content = '[{"id": 1, "title": "T", "url": "u", "reason": "r"}]'
    picks = _parse_picks(content)
    assert len(picks) == 1
    assert picks[0]["id"] == 1
    assert picks[0]["reason"] == "r"


def test_parse_picks_fenced_json():
    from mimir.scheduler.rss.filter import _parse_picks

    content = '```json\n[{"id": 2, "title": "A", "url": "b", "reason": "c"}]\n```'
    picks = _parse_picks(content)
    assert len(picks) == 1
    assert picks[0]["id"] == 2


def test_parse_picks_fenced_no_lang():
    from mimir.scheduler.rss.filter import _parse_picks

    content = '```\n[{"id": 3, "title": "X", "url": "y", "reason": "z"}]\n```'
    picks = _parse_picks(content)
    assert len(picks) == 1


def test_parse_picks_invalid_returns_empty():
    from mimir.scheduler.rss.filter import _parse_picks

    assert _parse_picks("not json at all") == []


def test_parse_picks_non_list_returns_empty():
    from mimir.scheduler.rss.filter import _parse_picks

    assert _parse_picks('{"id": 1}') == []


def test_parse_picks_prose_wrapped_json():
    from mimir.scheduler.rss.filter import _parse_picks

    content = 'Here are my selections: [{"id": 1, "title": "T", "url": "u", "reason": "r"}]'
    picks = _parse_picks(content)
    assert len(picks) == 1
    assert picks[0]["id"] == 1


@pytest.mark.asyncio
async def test_llm_filter_returns_parsed_picks():
    from mimir.scheduler.rss.filter import llm_filter

    mock_response = {
        "content": '[{"id": 1, "title": "T", "url": "u", "reason": "relevant"}]',
        "tool_calls": [],
        "finish_reason": "stop",
    }
    with patch("mimir.scheduler.rss.filter.llm_client") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        picks = await llm_filter([_entry()], semantic_memory="", feedback_summary="No feedback recorded yet.", n_picks=5)

    assert len(picks) == 1
    assert picks[0]["reason"] == "relevant"


@pytest.mark.asyncio
async def test_llm_filter_returns_empty_on_bad_response():
    from mimir.scheduler.rss.filter import llm_filter

    mock_response = {"content": "I cannot decide.", "tool_calls": [], "finish_reason": "stop"}
    with patch("mimir.scheduler.rss.filter.llm_client") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        picks = await llm_filter([_entry()], semantic_memory="", feedback_summary="No feedback recorded yet.", n_picks=5)

    assert picks == []
