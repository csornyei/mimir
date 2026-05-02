from pydantic_settings import SettingsConfigDict

from shared.config import SharedConfig


class MCPConfig(SharedConfig):
    model_config = SettingsConfigDict(env_file="mcp.env", env_file_encoding="utf-8")

    searxng_url: str = "http://localhost:8888"
    web_fetch_url: str = "http://localhost:8020/fetch"

    forgejo_url: str = ""
    forgejo_token: str = ""


mcp_config = MCPConfig()
