from mimir.config import SharedConfig


class SlackConfig(SharedConfig):
    slack_bot_token: str = ""
    slack_app_token: str = ""

    slack_dm_channel_id: str = ""
    slack_user_id: str = ""
    morning_brief_channel_id: str | None = None
    morning_brief_hour: int = 7
    newspaper_channel_id: str | None = None


slack_config = SlackConfig()
