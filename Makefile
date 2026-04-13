.PHONY: install test lint seed migrate docker-up docker-down quick-scan

PYTHON ?= python3.11
VENV := .venv

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -e ".[dev]"
	@echo "✓ Installed. Run: source $(VENV)/bin/activate"

test:
	$(VENV)/bin/python -m pytest src/tests/ -v

test-quick:
	$(VENV)/bin/python -m pytest src/tests/ -q

lint:
	$(VENV)/bin/python -m ruff check src/preflight/ src/tests/
	$(VENV)/bin/python -m ruff format --check src/preflight/ src/tests/

lint-fix:
	$(VENV)/bin/python -m ruff check --fix src/preflight/ src/tests/
	$(VENV)/bin/python -m ruff format src/preflight/ src/tests/

migrate:
	$(VENV)/bin/alembic upgrade head

migrate-create:
	$(VENV)/bin/alembic revision --autogenerate -m "$(msg)"

seed:
	$(VENV)/bin/python scripts/seed.py

docker-up:
	docker compose up -d

docker-down:
	docker compose down

quick-scan:
	$(VENV)/bin/python preflight quick-scan "$(REQUEST)"

full-assess:
	$(VENV)/bin/python preflight full-assess "$(REQUEST)" --heuristic-classify

clean:
	rm -rf .preflight/ *.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true