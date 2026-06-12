from typing import Optional

from shared.config import SharedConfig


class JobConfig(SharedConfig):
    timezone: Optional[str] = "Europe/Amsterdam"
    llm_model: Optional[str] = "gemma4:26b"
    agent_core_api_url: Optional[str] = None
    owner_name: str = "User"

    # RSS digest
    miniflux_url: Optional[str] = None
    miniflux_username: Optional[str] = None
    miniflux_password: Optional[str] = None
    rss_digest_min_entries: int = 10
    rss_digest_picks: int = 10


job_config = JobConfig()
