import re

import pytest

from agent_core.memory.semantic import SemanticMemory


@pytest.fixture
def mem(tmp_path):
    return SemanticMemory(vault_path=str(tmp_path / "memory.md"))


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


def test_read_returns_empty_when_file_missing(tmp_path):
    mem = SemanticMemory(vault_path=tmp_path / "nonexistent.md")
    assert mem.read() == ""


def test_read_returns_file_content(tmp_path):
    f = tmp_path / "memory.md"
    f.write_text("# Facts\n- User likes Python", encoding="utf-8")
    mem = SemanticMemory(vault_path=f)
    assert mem.read() == "# Facts\n- User likes Python"


async def test_read_utf8(tmp_path):
    f = tmp_path / "memory.md"
    f.write_text("Máté lives in Budapest", encoding="utf-8")
    mem = SemanticMemory(vault_path=f)
    saved_memory = await mem.read()
    assert "Máté" in saved_memory


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


def test_write_creates_file(mem, tmp_path):
    mem.write("# Memory\n- Fact one")
    assert (tmp_path / "memory.md").read_text(
        encoding="utf-8"
    ) == "# Memory\n- Fact one"


def test_write_overwrites_existing(mem, tmp_path):
    mem.write("first content")
    mem.write("second content")
    assert (tmp_path / "memory.md").read_text(encoding="utf-8") == "second content"


async def test_write_creates_parent_dirs(tmp_path):
    deep = SemanticMemory(vault_path=tmp_path / "nested" / "deep" / "memory.md")
    await deep.write("content")
    assert (tmp_path / "nested" / "deep" / "memory.md").exists()


# ---------------------------------------------------------------------------
# append_fact
# ---------------------------------------------------------------------------


def test_append_fact_creates_new_facts_section(mem, tmp_path):
    (tmp_path / "memory.md").write_text("# Existing content", encoding="utf-8")
    mem.append_fact("Likes coffee")
    content = (tmp_path / "memory.md").read_text(encoding="utf-8")
    assert "## New Facts" in content
    assert "Likes coffee" in content


def test_append_fact_appends_under_existing_section(mem, tmp_path):
    (tmp_path / "memory.md").write_text(
        "# Memory\n\n## New Facts\n- (2024-01-01) Old fact", encoding="utf-8"
    )
    mem.append_fact("New fact here")
    content = (tmp_path / "memory.md").read_text(encoding="utf-8")
    assert "Old fact" in content
    assert "New fact here" in content
    assert content.count("## New Facts") == 1


def test_append_fact_timestamp_format(mem, tmp_path):
    (tmp_path / "memory.md").write_text("", encoding="utf-8")
    mem.append_fact("Something important")
    content = (tmp_path / "memory.md").read_text(encoding="utf-8")
    assert re.search(r"\(\d{4}-\d{2}-\d{2}\)", content)


async def test_append_fact_when_file_missing_creates_it(tmp_path):
    mem = SemanticMemory(vault_path=tmp_path / "new.md")
    await mem.append_fact("First fact ever")
    content = (tmp_path / "new.md").read_text(encoding="utf-8")
    assert "First fact ever" in content
    assert "## New Facts" in content
