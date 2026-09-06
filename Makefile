UV_CACHE_DIR ?= /private/tmp/ops-intake-agent-uv-cache
export UV_CACHE_DIR

.PHONY: sync lint test-m0 test-m1 test test-security db-migrate seed reset-demo dev web-lint

sync:
	uv sync --dev

lint:
	uv run ruff check .
	uv run ruff format --check .
	pnpm --dir apps/web lint
	pnpm --dir apps/web typecheck

test-m0:
	uv run pytest -q tests/unit tests/security/test_architecture.py

db-migrate:
	uv run alembic upgrade head

seed:
	uv run python -m scripts.seed_demo

test-m1:
	uv run pytest -q tests/integration tests/security

test:
	uv run pytest -q

test-security:
	uv run pytest -q tests/security

reset-demo:
	uv run python -m scripts.reset_demo --confirm-reset

dev:
	docker compose up --build

web-lint:
	pnpm --dir apps/web lint
