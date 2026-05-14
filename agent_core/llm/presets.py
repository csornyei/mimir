from pathlib import Path

import yaml

from agent_core.config import agent_config
from shared.logger import logger
from shared.schemas import LLMPreset, PresetsResponse

_cache: PresetsResponse | None = None


def load_presets() -> PresetsResponse:
    """Load and validate presets from YAML; cached after first call."""
    global _cache
    if _cache is not None:
        return _cache

    path = Path(agent_config.llm_presets_path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        logger.warning("presets_file_not_found", path=str(path))
        _cache = _default_presets()
        return _cache
    except yaml.YAMLError as exc:
        logger.error("presets_yaml_parse_error", error=str(exc), path=str(path))
        _cache = _default_presets()
        return _cache

    try:
        raw_presets: dict = raw.get("presets") or {}
        if not raw_presets:
            raise ValueError("presets dict is empty")
        presets = {
            name: LLMPreset.model_validate(data) for name, data in raw_presets.items()
        }
        default_preset = raw.get("default_preset", "balanced")
        _cache = PresetsResponse(presets=presets, default_preset=default_preset)
    except Exception as exc:
        logger.error("presets_validation_error", error=str(exc))
        _cache = _default_presets()

    return _cache


def _default_presets() -> PresetsResponse:
    """Hardcoded fallback so the UI is never broken by a bad config file."""
    return PresetsResponse(
        presets={
            "balanced": LLMPreset(
                label="Balanced",
                enable_thinking=True,
                thinking_budget=2000,
                temperature=0.5,
                top_p=0.9,
                min_p=0.05,
                repetition_penalty=1.0,
                max_tokens=4096,
            )
        },
        default_preset="balanced",
    )
