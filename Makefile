.PHONY: install test lint fmt dev

install:
	uv sync
	@if [ -f web/package.json ]; then npm --prefix web ci; fi

test:
	uv run pytest
	@if [ -f web/package.json ]; then npm --prefix web test -- --run; fi

lint:
	uv run ruff check
	uv run ruff format --check
	@if [ -f web/package.json ]; then npm --prefix web run typecheck; fi

fmt:
	uv run ruff format
	uv run ruff check --fix

dev:
	@echo "API em :8000, front em :5173"
	(trap 'kill 0' INT; uv run uvicorn hachibu.app:from_env --factory --reload --port 8000 & \
	  npm --prefix web run dev & wait)
