from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MimirConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    owner_name: str = "Máté"
    llm_base_url: str = "http://localhost:8080"
    api_key: str | None = None
    llm_model: str = "google/gemma-4-E2B-it"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7

    semantic_memory_path: str = "vault/memory.md"
    vault_path: str = "vault"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mimir"

    agent_url: str = "http://127.0.0.1:8000"

    slack_bot_token: str = ""
    slack_app_token: str = ""

    # Approval flow
    approval_timeout_minutes: int = 10
    approval_discuss_timeout_hours: int = 24  # 0 = no timeout for DISCUSSING state
    slack_dm_channel_id: str = ""
    approval_reinvoke_llm: bool = True  # re-invoke LLM with tool result after approval
    write_tools: list[str] = Field(default_factory=list)

    @field_validator("write_tools", mode="before")
    @classmethod
    def _parse_write_tools(cls, v: object) -> object:
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v

    episodic_idle_minutes: int = 30
    episodic_retrieval_k: int = 3
    episodic_max_retries: int = 3
    episodic_new_messages_threshold: int = 5

    llm_context_window: int = 8192
    conversation_window_min: int = 2
    conversation_window_max: int = 20
    rag_max_tokens: int = 2000
    episodic_max_tokens: int = 600
    semantic_memory_max_tokens: int = 1500

    # Tool calling
    mcp_url: str = "http://localhost:8010"
    mcp_schema_cache_ttl_seconds: int = 300
    tool_max_steps: int = 5
    tool_call_timeout_seconds: int = 30


config = MimirConfig()
