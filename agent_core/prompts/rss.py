from typing import Any

from agent_core.prompts.loader import render


def render_rss_filter_system(n_picks: int) -> str:
    return render("rss_filter_system.j2", n_picks=n_picks)


def render_rss_filter_user(
    entries: list[dict[str, Any]],
    semantic_memory: str,
    feedback_summary: str,
    n_picks: int,
) -> str:
    return render(
        "rss_filter_user.j2",
        entries=entries,
        semantic_memory=semantic_memory,
        feedback_summary=feedback_summary,
        n_picks=n_picks,
    )
