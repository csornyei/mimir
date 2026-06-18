import re

import pytest

from agent_core.memory.semantic import SemanticMemory


@pytest.fixture
def mem(tmp_path, patch_file_api):
    return SemanticMemory(vault_path=str(tmp_path / "memory.md"))


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


async def test_read_returns_empty_when_file_missing(patch_file_api):
    patch_file_api.read_file.return_value = ""
    mem = SemanticMemory(vault_path="nonexistent.md")
    assert await mem.read() == ""


async def test_read_returns_file_content(patch_file_api):
    content = "# Facts\n- User likes Python"
    patch_file_api.read_file.return_value = content
    mem = SemanticMemory(vault_path="memory.md")
    assert await mem.read() == content


async def test_read_utf8(patch_file_api):
    content = "Máté lives in Budapest"
    patch_file_api.read_file.return_value = content
    mem = SemanticMemory(vault_path="memory.md")
    saved_memory = await mem.read()
    assert "Máté" in saved_memory


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


async def test_write_creates_file(patch_file_api):
    mem = SemanticMemory(vault_path="memory.md")
    await mem.write("# Memory\n- Fact one")
    patch_file_api.save_file.assert_called_once_with(
        "memory.md", "# Memory\n- Fact one"
    )


async def test_write_overwrites_existing(patch_file_api):
    mem = SemanticMemory(vault_path="memory.md")
    await mem.write("first content")
    await mem.write("second content")
    assert patch_file_api.save_file.call_count == 2
    patch_file_api.save_file.assert_called_with("memory.md", "second content")


async def test_write_creates_parent_dirs(patch_file_api):
    deep = SemanticMemory(vault_path="nested/deep/memory.md")
    await deep.write("content")
    patch_file_api.save_file.assert_called_once_with("nested/deep/memory.md", "content")


# ---------------------------------------------------------------------------
# append_fact
# ---------------------------------------------------------------------------


async def test_append_fact_creates_new_facts_section(patch_file_api):
    initial = "# Existing content"
    patch_file_api.read_file.return_value = initial
    mem = SemanticMemory(vault_path="memory.md")
    await mem.append_fact("Likes coffee")
    call_args = patch_file_api.save_file.call_args
    saved_content = call_args[0][1]
    assert "## New Facts" in saved_content
    assert "Likes coffee" in saved_content
    assert "# Existing content" in saved_content


async def test_append_fact_appends_under_existing_section(patch_file_api):
    initial = "# Memory\n\n## New Facts\n- (2024-01-01) Old fact"
    patch_file_api.read_file.return_value = initial
    mem = SemanticMemory(vault_path="memory.md")
    await mem.append_fact("New fact here")
    call_args = patch_file_api.save_file.call_args
    saved_content = call_args[0][1]
    assert "Old fact" in saved_content
    assert "New fact here" in saved_content
    assert saved_content.count("## New Facts") == 1


async def test_append_fact_timestamp_format(patch_file_api):
    patch_file_api.read_file.return_value = ""
    mem = SemanticMemory(vault_path="memory.md")
    await mem.append_fact("Something important")
    call_args = patch_file_api.save_file.call_args
    saved_content = call_args[0][1]
    assert re.search(r"\(\d{4}-\d{2}-\d{2}\)", saved_content)


async def test_append_fact_when_file_missing_creates_it(patch_file_api):
    patch_file_api.read_file.return_value = ""
    mem = SemanticMemory(vault_path="new.md")
    await mem.append_fact("First fact ever")
    call_args = patch_file_api.save_file.call_args
    saved_content = call_args[0][1]
    assert "First fact ever" in saved_content
    assert "## New Facts" in saved_content
