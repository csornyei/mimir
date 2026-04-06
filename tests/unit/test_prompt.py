import re
from datetime import datetime

from mimir.llm.prompt import build_system_prompt, format_episodic_context


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
