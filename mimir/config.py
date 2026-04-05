from pydantic_settings import BaseSettings, SettingsConfigDict


class MimirConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    owner_name: str = "Máté"
    llm_base_url: str = "http://localhost:8080"
    api_key: str | None = ""
    llm_model: str = "google/gemma-4-E2B-it"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7

    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dimension: int = 768

    semantic_memory_path: str = "vault/memory.md"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mimir"

    slack_bot_token: str
    slack_app_token: str


config = MimirConfig()
