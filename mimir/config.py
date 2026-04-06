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
    vault_path: str = "vault"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mimir"

    agent_url: str = "http://127.0.0.1:8000"

    slack_bot_token: str
    slack_app_token: str

    episodic_idle_minutes: int = 30
    episodic_retrieval_k: int = 3
    episodic_max_retries: int = 3
    episodic_new_messages_threshold: int = 5


config = MimirConfig()
