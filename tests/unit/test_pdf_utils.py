import pytest
import fitz

from agent_core.rag.sources.pdf import (
    _clean_text,
    _split_by_words,
    _token_estimate,
    chunk,
)


# ---------------------------------------------------------------------------
# _token_estimate
# ---------------------------------------------------------------------------


def test_token_estimate_basic():
    # 5 words → int(5 * 1.3) = 6
    assert _token_estimate("one two three four five") == 6


def test_token_estimate_empty():
    assert _token_estimate("") == 0


# ---------------------------------------------------------------------------
# _clean_text
# ---------------------------------------------------------------------------


def test_clean_text_joins_hyphenated_words():
    assert _clean_text("hyphen-\nated") == "hyphenated"


def test_clean_text_collapses_single_newlines():
    result = _clean_text("first line\nsecond line")
    assert result == "first line second line"


def test_clean_text_preserves_paragraph_breaks():
    result = _clean_text("para one\n\npara two")
    assert "para one" in result
    assert "para two" in result
    assert "\n\n" in result


def test_clean_text_collapses_multiple_spaces():
    assert _clean_text("too  many   spaces") == "too many spaces"


def test_clean_text_strips():
    assert _clean_text("  leading and trailing  ") == "leading and trailing"


# ---------------------------------------------------------------------------
# _split_by_words
# ---------------------------------------------------------------------------


def test_split_by_words_single_chunk_short_text():
    text = "short text here"
    result = _split_by_words(text, page=1, metadata={}, file_name="test.pdf")
    assert len(result) == 1
    text_out, meta = result[0]
    assert meta["page"] == 1
    assert "test" in text_out


def test_split_by_words_multiple_chunks_long_text():
    words = ["word"] * 500
    text = " ".join(words)
    result = _split_by_words(
        text, page=2, metadata={"source_type": "pdf"}, file_name="doc.pdf"
    )
    assert len(result) > 1
    for _, meta in result:
        assert meta["page"] == 2


def test_split_by_words_no_empty_chunks():
    text = " ".join(["w"] * 500)
    result = _split_by_words(text, page=1, metadata={}, file_name="f.pdf")
    for text_out, _ in result:
        assert text_out.strip() != ""


def test_split_by_words_metadata_carried():
    text = " ".join(["w"] * 500)
    base_meta = {"source_type": "pdf", "title": "My PDF"}
    result = _split_by_words(text, page=3, metadata=base_meta, file_name="f.pdf")
    for _, meta in result:
        assert meta["source_type"] == "pdf"
        assert meta["title"] == "My PDF"
        assert meta["page"] == 3


# ---------------------------------------------------------------------------
# chunk — uses a real tiny PDF created in memory
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_pdf(tmp_path):
    """Create a minimal single-page PDF with known content."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "This is a test PDF document with enough content to be indexed properly.",
    )
    path = tmp_path / "test.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def multipage_pdf(tmp_path):
    """Create a 3-page PDF; page 2 has very little text (should be skipped)."""
    doc = fitz.open()

    page1 = doc.new_page()
    page1.insert_text(
        (50, 72), "Page one has a full paragraph of interesting content here."
    )

    page2 = doc.new_page()
    page2.insert_text((50, 72), "Tiny")  # < 20 chars → skipped

    page3 = doc.new_page()
    page3.insert_text(
        (50, 72), "Page three also has a decent amount of readable text content."
    )

    path = tmp_path / "multi.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_chunk_returns_tuples(simple_pdf):
    result = chunk(simple_pdf, "test.pdf")
    assert len(result) > 0
    for text, meta in result:
        assert isinstance(text, str)
        assert isinstance(meta, dict)


def test_chunk_metadata_has_page(simple_pdf):
    result = chunk(simple_pdf, "test.pdf")
    for _, meta in result:
        assert "page" in meta
        assert meta["page"] == 1


def test_chunk_text_prefixed_with_stem(simple_pdf):
    result = chunk(simple_pdf, "test.pdf")
    for text, _ in result:
        assert text.startswith("test:")


def test_chunk_short_page_skipped(multipage_pdf):
    result = chunk(multipage_pdf, "multi.pdf")
    pages = {meta["page"] for _, meta in result}
    assert 2 not in pages  # page 2 has < 20 chars
    assert 1 in pages
    assert 3 in pages
