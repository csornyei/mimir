api:
	export SERVICE_NAME=agent-core && uv run fastapi dev agent_core/main.py --port 8000

mcp:
	export SERVICE_NAME=mcp-server && uv run python -m mcp_server.server

test:
	uv run pytest --cov

gemma:
	llama-server -hf unsloth/gemma-4-E4B-it-GGUF
