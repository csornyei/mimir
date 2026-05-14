from shared.config import SharedConfig


class AgentConfig(SharedConfig):
    owner_name: str = "Máté"
    llm_base_url: str = "http://localhost:8080"
    api_key: str | None = None
    llm_model: str = "google/gemma-4-E2B-it"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7

    embedding_url: str = "http://localhost:8081/v1/embeddings"
    embedding_model: str = "nomic-ai/nomic-embed-text-v2-moe"

    llm_context_window: int = 8192
    conversation_window_min: int = 2
    conversation_window_max: int = 20

    rag_max_tokens: int = 2000
    rag_top_k: int = 5
    rag_threshold: float = 0.6
    episodic_max_tokens: int = 600
    semantic_memory_max_tokens: int = 1500

    vault_path: str = "vault"
    agent_url: str = "http://127.0.0.1:8000"

    episodic_idle_minutes: int = 30
    episodic_retrieval_k: int = 3
    episodic_max_retries: int = 3
    episodic_new_messages_threshold: int = 5

    mcp_url: str = "http://localhost:8010"
    mcp_schema_cache_ttl_seconds: int = 300
    tool_max_steps: int = 5
    tool_call_timeout_seconds: int = 30

    approval_timeout_minutes: int = 10
    approval_discuss_timeout_hours: int = 24
    approval_reinvoke_llm: bool = True

    miniflux_url: str | None = None
    miniflux_username: str | None = None
    miniflux_password: str | None = None
    rss_digest_min_entries: int = 10
    rss_digest_picks: int = 10

    # Slack credentials used by agent_core scheduler and approval manager
    slack_bot_token: str = ""
    slack_dm_channel_id: str = ""
    slack_user_id: str = ""
    morning_brief_channel_id: str | None = None
    newspaper_channel_id: str | None = None

    llm_scheduler_model: str | None = None


agent_config = AgentConfig()
