from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class SharedConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mimir"
    semantic_memory_path: str = "vault/memory.md"

    caldav_url: Optional[str] = None
    caldav_username: Optional[str] = None
    caldav_password: Optional[str] = None
    default_calendar_name: Optional[str] = None

    env: str = "development"
    service_name: str = "mimir"
    otel_exporter_otlp_endpoint: str = "http://alloy:4317"
    llm_presets_path: str = "config/presets.yaml"
    environment: str = "homelab"

    weather_config_path: Optional[str] = None

    ntfy_url: Optional[str] = None
    ntfy_digest_topic: Optional[str] = None
    ntfy_morning_brief_topic: Optional[str] = None
    ntfy_messages_topic: Optional[str] = None
    ntfy_health_topic: str = "mimir-health-coach"
    mimir_host: Optional[str] = None


shared_config = SharedConfig()
