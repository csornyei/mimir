from fastapi import APIRouter, HTTPException
from httpx import AsyncClient, HTTPStatusError

from agent_core.config import agent_config
from agent_core.llm.presets import load_presets
from shared.logger import logger
from shared.schemas import ModelsResponse, OllamaModel, PresetsResponse

router = APIRouter()


async def _fetch_ollama_models() -> tuple[list[OllamaModel], set[str]]:
    """Fetch available and loaded models from Ollama.

    Returns (all_models, loaded_names).
    """
    async with AsyncClient(base_url=agent_config.llm_base_url, timeout=10.0) as client:
        try:
            tags_resp = await client.get("/api/tags")
            tags_resp.raise_for_status()
            tags_data = tags_resp.json()
        except HTTPStatusError as exc:
            logger.warning("ollama_tags_fetch_failed", error=str(exc))
            tags_data = {}
        except Exception as exc:
            logger.warning("ollama_tags_fetch_failed", error=str(exc))
            tags_data = {}

        try:
            ps_resp = await client.get("/api/ps")
            ps_resp.raise_for_status()
            ps_data = ps_resp.json()
        except Exception as exc:
            logger.warning("ollama_ps_fetch_failed", error=str(exc))
            ps_data = {}

    loaded_names: set[str] = {m.get("name", "") for m in (ps_data.get("models") or [])}

    models: list[OllamaModel] = [
        OllamaModel(
            name=m.get("name", ""),
            size=m.get("size"),
            modified_at=m.get("modified_at"),
            is_loaded=m.get("name", "") in loaded_names,
        )
        for m in (tags_data.get("models") or [])
        if m.get("name")
    ]

    return models, loaded_names


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """Return all Ollama models with loaded status and the configured default."""
    try:
        models, _ = await _fetch_ollama_models()
    except Exception as exc:
        logger.error("models_endpoint_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=502, detail="Failed to fetch models from Ollama"
        )

    return ModelsResponse(models=models, default_model=agent_config.llm_model)


@router.get("/presets", response_model=PresetsResponse)
async def list_presets() -> PresetsResponse:
    """Return all configured LLM presets."""
    return load_presets()
