import re

_HEADER_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

_WORDS_PER_TOKEN = 1.3
_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 50
_CHUNK_WORDS = int(_CHUNK_TOKENS / _WORDS_PER_TOKEN)  # ~393
_OVERLAP_WORDS = int(_OVERLAP_TOKENS / _WORDS_PER_TOKEN)  # ~38


def _token_estimate(text: str) -> int:
    return int(len(text.split()) * _WORDS_PER_TOKEN)


def _split_by_words(text: str, header_path: str) -> list[tuple[str, dict]]:
    """Split a long text block into word-budget chunks with overlap."""
    words = text.split()
    chunks: list[tuple[str, dict]] = []
    start = 0
    while start < len(words):
        end = start + _CHUNK_WORDS
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            chunks.append((chunk_text, {"header": header_path}))
        start += _CHUNK_WORDS - _OVERLAP_WORDS
    return chunks


def chunk(text: str) -> list[tuple[str, dict]]:
    """
    Split Obsidian-flavoured Markdown into chunks.

    Strategy:
    1. Split on H2/H3 headers; each section becomes a candidate chunk.
    2. Sections that exceed ~512 tokens are further split by word count
       with ~50-token overlap.

    Returns list of (chunk_text, metadata) where metadata contains the
    header path that produced the chunk.
    """
    # Find all header positions
    headers = list(_HEADER_RE.finditer(text))

    if not headers:
        # No headers — treat entire document as one section
        sections = [("", text)]
    else:
        sections: list[tuple[str, str]] = []
        for i, match in enumerate(headers):
            header_text = match.group(2).strip()
            section_start = match.end()
            section_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            body = text[section_start:section_end].strip()
            sections.append((header_text, body))

    chunks: list[tuple[str, dict]] = []
    for header, body in sections:
        if not body:
            continue
        if _token_estimate(body) <= _CHUNK_TOKENS:
            chunks.append((body, {"header": header}))
        else:
            chunks.extend(_split_by_words(body, header))

    return chunks
