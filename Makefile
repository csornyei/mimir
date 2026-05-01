api:
	export SERVICE_NAME=agent-core && uv run fastapi dev agent_core/main.py --port 8000

mcp:
	export SERVICE_NAME=mcp-server && uv run python -m mcp_server.server

slack:
	kubectl scale deployment mimir-slack --replicas 0 -n mimir && \
	trap 'kubectl scale deployment mimir-slack --replicas 1 -n mimir' EXIT; \
	export SERVICE_NAME=slack-bot && uv run python -m slackbot.bot

test:
	uv run pytest --cov

gemma:
	llama-server -hf unsloth/gemma-4-E4B-it-GGUF
