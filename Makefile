UV_CACHE_DIR ?= /private/tmp/ops-intake-agent-uv-cache
export UV_CACHE_DIR

.PHONY: sync lint test-m0 test-m1 test-m2 test-m3 test-m4 test-m5 test-m6 test-m7 test-m8 test-m9 test-m10 test-m11 test test-security db-migrate seed reset-demo dev web-lint generate-fixtures eval-fake eval-live security-scan

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

test-m2:
	uv run pytest -q tests/unit/test_artifact_safety.py tests/integration/test_artifacts.py tests/security

test-m3:
	uv run pytest -q tests/unit/test_parsers.py

test-m4:
	uv run pytest -q tests/unit/test_canonical_domain.py tests/unit/test_validation.py

test-m5:
	uv run pytest -q tests/unit/test_extraction_verification.py tests/unit/test_extraction_service.py tests/unit/test_model_providers.py

test-m6:
	uv run pytest -q tests/unit/test_sop_domain.py tests/integration/test_retrieval.py

test-m7:
	uv run pytest -q tests/workflow tests/integration/test_workflow_runs.py

test-m8:
	uv run pytest -q tests/integration/test_review_api.py

test-m9:
	uv run pytest -q tests/integration/test_operations_api.py

test-m10:
	uv run pytest -q tests/evaluation

test-m11:
	uv run pytest -q tests/security tests/integration/test_identity.py

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

generate-fixtures:
	uv run python -m scripts.generate_synthetic_fixtures

eval-fake:
	uv run python -m scripts.run_eval --provider fake

eval-live:
	uv run python -m scripts.run_eval --provider live $(LIVE_EVAL_ARGS)

security-scan:
	uv run python -m scripts.security_scan
