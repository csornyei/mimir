from shared.config import SharedConfig


class SlackConfig(SharedConfig):
    slack_bot_token: str = ""
    slack_app_token: str = ""

    slack_dm_channel_id: str = ""
    slack_user_id: str = ""
    morning_brief_channel_id: str | None = None
    newspaper_channel_id: str | None = None

    mcp_url: str = "http://localhost:8010"
    agent_url: str = "http://localhost:8000"


slack_config = SlackConfig()
