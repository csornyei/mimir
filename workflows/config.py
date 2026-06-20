from typing import Optional

from shared.config import SharedConfig


class WorkflowConfig(SharedConfig):
    timezone: Optional[str] = "Europe/Amsterdam"
    llm_model: Optional[str] = "gemma4:26b"
    agent_core_api_url: Optional[str] = None
    owner_name: str = "User"

    # RSS digest
    miniflux_url: Optional[str] = None
    miniflux_username: Optional[str] = None
    miniflux_password: Optional[str] = None
    rss_article_max_tokens: int = 4000
    rss_digest_score_threshold: float = 7.0
    rss_summarizer_concurrency: int = 5

    # Health coach
    health_coach_endpoint_url: Optional[str] = None
    health_coach_type: str = "week"
    health_memory_file_path: str = "vault/mem_health.md"


workflow_config = WorkflowConfig()
