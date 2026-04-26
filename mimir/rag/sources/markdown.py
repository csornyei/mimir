import re
import html
import yaml
from pathlib import Path

from mimir.logger import logger


_HEADER_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

_WORDS_PER_TOKEN = 1.3
_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 50
_CHUNK_WORDS = int(_CHUNK_TOKENS / _WORDS_PER_TOKEN)  # ~393
_OVERLAP_WORDS = int(_OVERLAP_TOKENS / _WORDS_PER_TOKEN)  # ~38


def _token_estimate(text: str) -> int:
    return int(len(text.split()) * _WORDS_PER_TOKEN)


def _cleanup_links(text: str) -> str:
    # Remove Obsidian-style links [[Page Name]] or [[Page Name|Alias]]
    return re.sub(r"\[\[([^|\]]+\|)?([^\]]+)\]\]", r"\2", text)


def _cleanup_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _extract_tags(text: str) -> tuple[list[str], str]:
    tags_re = re.compile(r"#([a-zA-Z0-9_/-]+)")

    tags = tags_re.findall(text)
    text_without_tags = tags_re.sub("", text)

    return (tags, text_without_tags.strip())


def _extract_frontmatter(text: str) -> tuple[dict, str]:
    frontmatter_re = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
    match = frontmatter_re.match(text)
    if not match:
        return ({}, text)

    frontmatter_str = match.group(1)
    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError as e:
        logger.warning("markdown_frontmatter_parse_failed", error=str(e), exc_info=True)
        frontmatter = {}

    text_without_frontmatter = text[match.end() :].strip()

    return (frontmatter, text_without_frontmatter)


def _split_by_words(
    text: str, header_path: str, metadata: dict, title: str = ""
) -> list[tuple[str, dict]]:
    """Split a long text block into word-budget chunks with overlap."""
    words = text.split()
    chunks: list[tuple[str, dict]] = []
    start = 0
    while start < len(words):
        end = start + _CHUNK_WORDS
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            chunks.append(
                (f"{title}: {chunk_text}", {**metadata, "header": header_path})
            )
        start += _CHUNK_WORDS - _OVERLAP_WORDS
    return chunks


def chunk(text: str, file_name: str) -> list[tuple[str, dict]]:
    """
    Split Obsidian-flavoured Markdown into chunks.

    Strategy:
    1. Split on H2/H3 headers; each section becomes a candidate chunk.
    2. Sections that exceed ~512 tokens are further split by word count
       with ~50-token overlap.

    Returns list of (chunk_text, metadata) where metadata contains the
    header path that produced the chunk.
    """

    title = Path(file_name).stem.replace("_", " ").replace("-", " ")

    tags, text = _extract_tags(text)
    frontmatter, text = _extract_frontmatter(text)

    if frontmatter and "tags" in frontmatter:
        tags.extend(frontmatter["tags"])
        del frontmatter["tags"]

    metadata = {"file_name": file_name, "tags": tags, **frontmatter}

    # Find all header positions
    headers = list(_HEADER_RE.finditer(text))

    if not headers:
        # No headers — treat entire document as one section
        text = _cleanup_links(_cleanup_html(text))
        sections = [("", text)]
    else:
        sections: list[tuple[str, str]] = []
        for i, match in enumerate(headers):
            header_text = match.group(2).strip()
            section_start = match.end()
            section_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            body = text[section_start:section_end].strip()
            body = _cleanup_links(body)
            body = _cleanup_html(body)

            sections.append((header_text, body))

    chunks: list[tuple[str, dict]] = []
    for header, body in sections:
        chunk_metadata = {**metadata, "header": header}
        if not body:
            continue
        if _token_estimate(body) <= _CHUNK_TOKENS:
            chunks.append((f"{title}: {body}", chunk_metadata))
        else:
            chunks.extend(_split_by_words(body, header, chunk_metadata, title=title))

    return chunks
