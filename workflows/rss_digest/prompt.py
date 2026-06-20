from typing import Any

from shared.prompts.loader import render


def render_rss_article_summarize(
    title: str,
    feed_name: str | None,
    category: str | None,
    url: str,
    content: str,
    semantic_memory: str,
) -> str:
    return render(
        "rss_article_summarize.j2",
        title=title,
        feed_name=feed_name,
        category=category,
        url=url,
        content=content,
        semantic_memory=semantic_memory,
    )


def build_summarize_prompt(
    article: dict[str, Any],
    semantic_memory: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "user",
            "content": render_rss_article_summarize(
                title=str(article.get("title", "")),
                feed_name=article.get("feed_name"),
                category=article.get("category"),
                url=str(article.get("url", "")),
                content=str(article.get("content", "")),
                semantic_memory=semantic_memory,
            ),
        },
    ]
