api:
	export SERVICE_NAME=agent-core && uv run fastapi dev mimir/main.py --port 8000

mcp:
	export SERVICE_NAME=mcp-server && uv run python -m mimir.mcp.server

slack:
	export SERVICE_NAME=slack-bot && uv run python -m mimir.interfaces.slack.bot

test:
	uv run pytest --cov=mimir

gemma:
	llama-server -hf unsloth/gemma-4-E4B-it-GGUF
