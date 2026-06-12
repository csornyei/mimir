from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.rss_digest.filter import _build_prompt, _parse_picks, llm_filter


def _entry(entry_id: int = 1, title: str = "Test Article") -> dict:
    return {
        "id": entry_id,
        "title": title,
        "url": f"https://example.com/{entry_id}",
        "feed_name": "Tech Blog",
        "category": "Technology",
        "summary": "A brief summary of the article.",
    }


def test_build_prompt_includes_entry_title() -> None:
    messages = _build_prompt(
        [_entry()],
        semantic_memory="User likes Python.",
        feedback_summary="No feedback.",
        n_picks=5,
    )
    assert "Test Article" in messages[1]["content"]


def test_build_prompt_includes_semantic_memory() -> None:
    messages = _build_prompt(
        [_entry()],
        semantic_memory="User likes Python.",
        feedback_summary="No feedback.",
        n_picks=5,
    )
    assert "User likes Python." in messages[1]["content"]


def test_build_prompt_omits_memory_section_when_empty() -> None:
    messages = _build_prompt(
        [_entry()],
        semantic_memory="",
        feedback_summary="No feedback recorded yet.",
        n_picks=5,
    )
    assert "About the user" not in messages[1]["content"]


def test_build_prompt_omits_feedback_section_when_no_data() -> None:
    messages = _build_prompt(
        [_entry()],
        semantic_memory="",
        feedback_summary="No feedback recorded yet.",
        n_picks=5,
    )
    assert "Past feedback" not in messages[1]["content"]


def test_build_prompt_includes_feedback_when_present() -> None:
    messages = _build_prompt(
        [_entry()],
        semantic_memory="",
        feedback_summary="You like Python articles.",
        n_picks=5,
    )
    assert "Past feedback" in messages[1]["content"]
    assert "You like Python articles." in messages[1]["content"]


def test_parse_picks_plain_json() -> None:
    picks = _parse_picks('[{"id": 1, "title": "T", "url": "u", "reason": "r"}]')
    assert len(picks) == 1
    assert picks[0]["id"] == 1
    assert picks[0]["reason"] == "r"


def test_parse_picks_fenced_json() -> None:
    picks = _parse_picks(
        '```json\n[{"id": 2, "title": "A", "url": "b", "reason": "c"}]\n```'
    )
    assert len(picks) == 1
    assert picks[0]["id"] == 2


def test_parse_picks_fenced_no_lang() -> None:
    picks = _parse_picks(
        '```\n[{"id": 3, "title": "X", "url": "y", "reason": "z"}]\n```'
    )
    assert len(picks) == 1


def test_parse_picks_invalid_returns_empty() -> None:
    assert _parse_picks("not json at all") == []


def test_parse_picks_non_list_returns_empty() -> None:
    assert _parse_picks('{"id": 1}') == []


def test_parse_picks_prose_wrapped_json() -> None:
    content = (
        'Here are my selections: [{"id": 1, "title": "T", "url": "u", "reason": "r"}]'
    )
    picks = _parse_picks(content)
    assert len(picks) == 1
    assert picks[0]["id"] == 1


def test_parse_picks_skips_string_list_finds_object_list() -> None:
    # Model emits a draft list of strings, reconsiders, then emits the correct objects
    content = (
        '```json\n["1: 1", "2: 2"]\n```\n\nWait, here is the proper format:\n'
        '```json\n[{"id": 1, "title": "T", "url": "u", "reason": "r"}]\n```'
    )
    picks = _parse_picks(content)
    assert len(picks) == 1
    assert picks[0]["id"] == 1


@pytest.mark.asyncio
async def test_llm_filter_returns_parsed_picks() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "content": '[{"id": 1, "title": "T", "url": "u", "reason": "relevant"}]'
        }
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", mock_cls):
        picks = await llm_filter(
            [_entry()],
            semantic_memory="",
            feedback_summary="No feedback recorded yet.",
            n_picks=5,
        )

    assert len(picks) == 1
    assert picks[0]["reason"] == "relevant"


@pytest.mark.asyncio
async def test_llm_filter_returns_empty_on_bad_response() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"content": "I cannot decide."})
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", mock_cls):
        picks = await llm_filter(
            [_entry()],
            semantic_memory="",
            feedback_summary="No feedback recorded yet.",
            n_picks=5,
        )

    assert picks == []
