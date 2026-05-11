from dataclasses import dataclass

from shared.schemas import LLMSettings


@dataclass
class LLMParams:
    """Internal LLM dispatch params. All fields default to None (= use config default)."""

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    min_p: float | None = None
    repetition_penalty: float | None = None
    enable_thinking: bool | None = None
    thinking_budget: int | None = None


def llm_params_from_settings(settings: LLMSettings | None) -> LLMParams:
    """Convert a UI LLMSettings object to internal LLMParams."""
    if settings is None:
        return LLMParams()
    return LLMParams(
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
        min_p=settings.min_p,
        repetition_penalty=settings.repetition_penalty,
        enable_thinking=settings.enable_thinking,
        thinking_budget=settings.thinking_budget,
    )
