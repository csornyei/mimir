from mimir.rag.sources.markdown import (
    _cleanup_html,
    _cleanup_links,
    _extract_frontmatter,
    _extract_tags,
    _split_by_words,
    _token_estimate,
    chunk,
)


# ---------------------------------------------------------------------------
# _token_estimate
# ---------------------------------------------------------------------------


def test_token_estimate_basic():
    # 10 words → int(10 * 1.3) = 13
    assert _token_estimate("one two three four five six seven eight nine ten") == 13


def test_token_estimate_empty():
    assert _token_estimate("") == 0


# ---------------------------------------------------------------------------
# _cleanup_links
# ---------------------------------------------------------------------------


def test_cleanup_links_simple():
    assert _cleanup_links("[[Page Name]]") == "Page Name"


def test_cleanup_links_alias():
    assert _cleanup_links("[[Page Name|Alias]]") == "Alias"


def test_cleanup_links_multiple():
    result = _cleanup_links("See [[Alpha]] and [[Beta|B]].")
    assert "Alpha" in result
    assert "B" in result
    assert "[[" not in result


def test_cleanup_links_no_links():
    assert _cleanup_links("plain text") == "plain text"


# ---------------------------------------------------------------------------
# _cleanup_html
# ---------------------------------------------------------------------------


def test_cleanup_html_removes_tags():
    assert _cleanup_html("<b>bold</b>") == "bold"


def test_cleanup_html_unescapes_entities():
    assert _cleanup_html("&amp; &lt; &gt;") == "& < >"


def test_cleanup_html_nested_tags():
    assert _cleanup_html("<p><em>text</em></p>") == "text"


def test_cleanup_html_no_html():
    assert _cleanup_html("plain text") == "plain text"


# ---------------------------------------------------------------------------
# _extract_tags
# ---------------------------------------------------------------------------


def test_extract_tags_finds_tags():
    tags, text = _extract_tags("some text #tag1 and #nested/tag here")
    assert "tag1" in tags
    assert "nested/tag" in tags


def test_extract_tags_removes_from_text():
    _, text = _extract_tags("before #mytag after")
    assert "#mytag" not in text
    assert "before" in text
    assert "after" in text


def test_extract_tags_no_tags():
    tags, text = _extract_tags("no tags here")
    assert tags == []
    assert text == "no tags here"


def test_extract_tags_multiple():
    tags, _ = _extract_tags("#a #b #c")
    assert sorted(tags) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# _extract_frontmatter
# ---------------------------------------------------------------------------


def test_extract_frontmatter_parses_yaml():
    content = "---\ntitle: Test\nauthor: Me\n---\nBody text"
    fm, body = _extract_frontmatter(content)
    assert fm == {"title": "Test", "author": "Me"}
    assert body == "Body text"


def test_extract_frontmatter_no_frontmatter():
    content = "Just body text"
    fm, body = _extract_frontmatter(content)
    assert fm == {}
    assert body == "Just body text"


def test_extract_frontmatter_invalid_yaml():
    content = "---\nkey: [unclosed bracket\n---\nBody"
    fm, body = _extract_frontmatter(content)
    assert fm == {}
    assert body == "Body"


def test_extract_frontmatter_empty_block():
    content = "---\n\n---\nBody"
    fm, body = _extract_frontmatter(content)
    assert isinstance(fm, dict)
    assert body == "Body"


# ---------------------------------------------------------------------------
# _split_by_words
# ---------------------------------------------------------------------------


def test_split_by_words_short_text_single_chunk():
    text = "short text"
    chunks = _split_by_words(text, "H", {}, title="T")
    assert len(chunks) == 1
    assert chunks[0][1]["header"] == "H"
    assert "T:" in chunks[0][0]


def test_split_by_words_long_text_multiple_chunks():
    words = ["word"] * 600
    text = " ".join(words)
    chunks = _split_by_words(text, "Header", {"file_name": "f.md"}, title="Doc")
    assert len(chunks) > 1


def test_split_by_words_metadata_carried():
    text = " ".join(["w"] * 600)
    meta = {"file_name": "test.md", "tags": ["a"]}
    chunks = _split_by_words(text, "H", meta, title="T")
    for _, m in chunks:
        assert m["file_name"] == "test.md"
        assert m["header"] == "H"


def test_split_by_words_no_empty_chunks():
    text = " ".join(["w"] * 600)
    chunks = _split_by_words(text, "H", {}, title="T")
    for text_out, _ in chunks:
        assert text_out.strip() != ""


# ---------------------------------------------------------------------------
# chunk (integration of the full pipeline)
# ---------------------------------------------------------------------------


def test_chunk_no_headers_single_chunk():
    text = "This is a simple document without any headers."
    result = chunk(text, "test.md")
    assert len(result) == 1
    text_out, meta = result[0]
    assert "test" in text_out.lower()
    assert meta["file_name"] == "test.md"


def test_chunk_h2_split():
    text = "## Section One\nContent of section one.\n## Section Two\nContent of section two."
    result = chunk(text, "doc.md")
    assert len(result) == 2
    headers = [m["header"] for _, m in result]
    assert "Section One" in headers
    assert "Section Two" in headers


def test_chunk_h3_split():
    text = "### Sub A\nContent A.\n### Sub B\nContent B."
    result = chunk(text, "doc.md")
    assert len(result) == 2


def test_chunk_large_section_produces_multiple_chunks():
    body = " ".join(["word"] * 600)
    text = f"## Big Section\n{body}"
    result = chunk(text, "big.md")
    assert len(result) > 1


def test_chunk_empty_section_skipped():
    text = "## Empty Section\n## Non-empty Section\nActual content here."
    result = chunk(text, "test.md")
    assert len(result) == 1
    _, meta = result[0]
    assert meta["header"] == "Non-empty Section"


def test_chunk_frontmatter_tags_merged():
    text = "---\ntitle: My Note\ntags: [foo, bar]\n---\n## Section\nContent"
    result = chunk(text, "note.md")
    assert len(result) == 1
    _, meta = result[0]
    assert "foo" in meta["tags"]
    assert "bar" in meta["tags"]


def test_chunk_obsidian_links_cleaned():
    text = "## Section\nSee [[Other Page|alias]] for details."
    result = chunk(text, "note.md")
    assert len(result) == 1
    text_out, _ = result[0]
    assert "alias" in text_out
    assert "[[" not in text_out


def test_chunk_file_name_stem_used_as_title():
    text = "## Section\nSome content here."
    result = chunk(text, "my_cool_note.md")
    text_out, _ = result[0]
    assert "my cool note" in text_out.lower()


def test_chunk_html_cleaned():
    text = "## Section\n<b>Bold text</b> and &amp; entity."
    result = chunk(text, "note.md")
    text_out, _ = result[0]
    assert "<b>" not in text_out
    assert "&amp;" not in text_out
    assert "Bold text" in text_out
