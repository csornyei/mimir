from shared.prompts.loader import render


def render_episodic_consolidation_initial(transcript: str) -> str:
    return render("episodic_consolidation_initial.j2", transcript=transcript)


def render_episodic_consolidation_update(prior_summary: str, transcript: str) -> str:
    return render(
        "episodic_consolidation_update.j2",
        prior_summary=prior_summary,
        transcript=transcript,
    )
