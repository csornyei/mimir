from pydantic_settings import SettingsConfigDict

from mimir.config import SharedConfig


class MCPConfig(SharedConfig):
    model_config = SettingsConfigDict(env_file="mcp.env", env_file_encoding="utf-8")

    searxng_url: str = "http://localhost:8888"


mcp_config = MCPConfig()
