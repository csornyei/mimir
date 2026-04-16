from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.mcp", env_file_encoding="utf-8")

    searxng_url: str = "http://localhost:8888"
    semantic_memory_path: str = "vault/memory.md"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mimir"


mcp_config = MCPConfig()
