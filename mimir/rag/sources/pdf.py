from pathlib import Path

import fitz  # pymupdf

_WORDS_PER_TOKEN = 1.3
_CHUNK_TOKENS = 400
_OVERLAP_TOKENS = 50
_CHUNK_WORDS = int(_CHUNK_TOKENS / _WORDS_PER_TOKEN)  # ~307
_OVERLAP_WORDS = int(_OVERLAP_TOKENS / _WORDS_PER_TOKEN)  # ~38


def _token_estimate(text: str) -> int:
    return int(len(text.split()) * _WORDS_PER_TOKEN)


def _split_by_words(text: str, page: int) -> list[tuple[str, dict]]:
    words = text.split()
    chunks: list[tuple[str, dict]] = []
    start = 0
    while start < len(words):
        end = start + _CHUNK_WORDS
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            chunks.append((chunk_text, {"page": page}))
        start += _CHUNK_WORDS - _OVERLAP_WORDS
    return chunks


def chunk(path: Path) -> list[tuple[str, dict]]:
    """
    Extract and chunk text from a PDF using pymupdf.

    Strategy:
    1. Extract text page by page.
    2. Split each page on paragraph boundaries (double newline).
    3. Paragraphs that exceed ~400 tokens are further split by word count
       with ~50-token overlap.

    Returns list of (chunk_text, metadata) where metadata contains the
    page number (1-indexed).
    """
    chunks: list[tuple[str, dict]] = []

    with fitz.open(str(path)) as doc:
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]

            for para in paragraphs:
                if _token_estimate(para) <= _CHUNK_TOKENS:
                    chunks.append((para, {"page": page_num}))
                else:
                    chunks.extend(_split_by_words(para, page_num))

    return chunks
