"""Token counting and truncation backed by tiktoken.

Uses the ``cl100k_base`` encoding as a model-agnostic approximation. It is not
exact for every model's tokenizer, but it is far closer than a char/4 heuristic
and consistent across the codebase.
"""

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Return *text* truncated to at most *max_tokens* tokens."""
    if max_tokens <= 0:
        return ""
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _ENCODING.decode(tokens[:max_tokens])
