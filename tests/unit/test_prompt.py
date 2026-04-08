import re
from datetime import datetime

from mimir.llm.prompt import (
    build_system_prompt,
    format_episodic_context,
    token_estimate,
    trim_to_tokens,
)


# ---------------------------------------------------------------------------
# token_estimate
# ---------------------------------------------------------------------------


def test_token_estimate_empty():
    assert token_estimate("") == 0


def test_token_estimate_four_chars_is_one_token():
    assert token_estimate("abcd") == 1


def test_token_estimate_rounds_down():
    # 10 chars → 10 // 4 = 2
    assert token_estimate("0123456789") == 2


def test_token_estimate_long_text():
    text = "a" * 400
    assert token_estimate(text) == 100


# ---------------------------------------------------------------------------
# trim_to_tokens
# ---------------------------------------------------------------------------


def test_trim_to_tokens_short_text_unchanged():
    text = "hello world"
    assert trim_to_tokens(text, 100) == text


def test_trim_to_tokens_exact_fit_unchanged():
    # 8 chars → 2 tokens; max_tokens=2 → no trim
    text = "abcdefgh"
    assert trim_to_tokens(text, 2) == text


def test_trim_to_tokens_truncates_long_text():
    # 40 chars → 10 tokens; cap at 2 → should truncate
    text = "word " * 8  # 40 chars → 10 tokens
    result = trim_to_tokens(text, 2)
    assert len(result) < len(text)


def test_trim_to_tokens_appends_suffix():
    text = "word " * 8
    result = trim_to_tokens(text, 2)
    assert result.endswith("[... truncated]")


def test_trim_to_tokens_cuts_at_word_boundary():
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    result = trim_to_tokens(text, 5)  # 5 tokens = 20 chars
    assert result.endswith(" [... truncated]")
    without_suffix = result.removesuffix(" [... truncated]")
    # The character immediately after the cut in the original must be a space,
    # confirming the cut landed at a word boundary.
    assert text[len(without_suffix)] == " "


def test_trim_to_tokens_zero_max_tokens():
    result = trim_to_tokens("any text", 0)
    assert result == "[... truncated]"


def test_trim_to_tokens_empty_text_unchanged():
    assert trim_to_tokens("", 100) == ""


# ---------------------------------------------------------------------------
# format_episodic_context
# ---------------------------------------------------------------------------


def test_format_episodic_context_empty_list():
    result = format_episodic_context([])
    assert result == "No relevant past conversations found."


def test_format_episodic_context_single_entry():
    memories = [{"started_at": datetime(2024, 3, 1), "summary": "Discussed Python project"}]
    result = format_episodic_context(memories)
    assert "2024-03-01" in result
    assert "Discussed Python project" in result


def test_format_episodic_context_multiple_entries():
    memories = [
        {"started_at": datetime(2024, 3, 1), "summary": "First conversation"},
        {"started_at": datetime(2024, 3, 5), "summary": "Second conversation"},
    ]
    result = format_episodic_context(memories)
    assert "First conversation" in result
    assert "Second conversation" in result
    assert "2024-03-01" in result
    assert "2024-03-05" in result


def test_format_episodic_context_none_started_at():
    memories = [{"started_at": None, "summary": "Unknown date entry"}]
    result = format_episodic_context(memories)
    assert "unknown date" in result
    assert "Unknown date entry" in result


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


def test_build_system_prompt_contains_owner():
    prompt = build_system_prompt(owner="Alice", semantic_memory="Alice likes Python")
    assert "Alice" in prompt


def test_build_system_prompt_contains_semantic_memory():
    prompt = build_system_prompt(owner="Bob", semantic_memory="Bob works at Acme Corp")
    assert "Bob works at Acme Corp" in prompt


def test_build_system_prompt_empty_memory_uses_fallback():
    prompt = build_system_prompt(owner="Bob", semantic_memory="")
    assert "No semantic memory loaded yet." in prompt


def test_build_system_prompt_none_memory_uses_fallback():
    prompt = build_system_prompt(owner="Bob", semantic_memory=None)
    assert "No semantic memory loaded yet." in prompt


def test_build_system_prompt_empty_rag_uses_fallback():
    prompt = build_system_prompt(owner="Bob", semantic_memory="x", rag_context="")
    assert "No relevant documents retrieved." in prompt


def test_build_system_prompt_empty_episodic_uses_fallback():
    prompt = build_system_prompt(owner="Bob", semantic_memory="x", episodic_context="")
    assert "No relevant past conversations found." in prompt


def test_build_system_prompt_provided_rag_context():
    prompt = build_system_prompt(
        owner="Bob", semantic_memory="x", rag_context="Some document content"
    )
    assert "Some document content" in prompt


def test_build_system_prompt_provided_episodic_context():
    prompt = build_system_prompt(
        owner="Bob", semantic_memory="x", episodic_context="Past conversation summary"
    )
    assert "Past conversation summary" in prompt


def test_build_system_prompt_context_window_injected():
    prompt = build_system_prompt(owner="Bob", semantic_memory="x", context_window=32000)
    assert "32000" in prompt


def test_build_system_prompt_contains_date():
    prompt = build_system_prompt(owner="Bob", semantic_memory="x")
    assert re.search(r"\d{4}-\d{2}-\d{2}", prompt)


def test_build_system_prompt_trims_very_long_semantic_memory():
    # 25 000 chars → ~6 250 tokens, well over the 1 500-token default cap
    long_memory = "word " * 5000
    prompt = build_system_prompt(owner="Bob", semantic_memory=long_memory)
    assert "[... truncated]" in prompt
    assert long_memory not in prompt


def test_build_system_prompt_trims_very_long_episodic_context():
    # 5 000 chars → ~1 250 tokens, over the 600-token default cap
    long_episodic = "entry " * 1000
    prompt = build_system_prompt(
        owner="Bob", semantic_memory="x", episodic_context=long_episodic
    )
    assert "[... truncated]" in prompt
    assert long_episodic not in prompt


def test_build_system_prompt_short_inputs_not_truncated():
    short_memory = "Alice likes Python."
    short_episodic = "Talked about databases."
    prompt = build_system_prompt(
        owner="Alice",
        semantic_memory=short_memory,
        episodic_context=short_episodic,
    )
    assert short_memory in prompt
    assert short_episodic in prompt
    assert "[... truncated]" not in prompt
