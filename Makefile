api:
	uv run fastapi dev mimir/main.py --port 8000

mcp:
	uv run python -m mimir.mcp.server

slack:
	uv run python -m mimir.interfaces.slack.bot

test:
	uv run pytest --cov=mimir

gemma:
	llama-server -hf unsloth/gemma-4-E4B-it-GGUF
