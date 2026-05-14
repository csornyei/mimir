from typing import Optional

from shared.config import SharedConfig


class JobConfig(SharedConfig):
    timezone: Optional[str] = "Europe/Amsterdam"
    llm_model: Optional[str] = "gemma4:26b"
    agent_core_api_url: Optional[str] = None
    owner_name: str = "User"


job_config = JobConfig()
