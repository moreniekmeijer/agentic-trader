VENV_DIR := .venv
PYTHON := python3

.PHONY: all venv install sync lint format typecheck test run run-worker clean reset

# ------------------------
# DEFAULT
# ------------------------
all: install format lint typecheck test

# ------------------------
# ENVIRONMENT
# ------------------------
$(VENV_DIR):
	@echo "Creating virtual environment in $(VENV_DIR)..."
	uv python install
	uv venv $(VENV_DIR)

venv: $(VENV_DIR)

install: $(VENV_DIR)
	@echo "Installing dependencies..."
	uv sync

sync:
	@echo "Syncing dependencies..."
	uv sync

# ------------------------
# CODE QUALITY
# ------------------------
lint:
	@echo "Running Ruff checks..."
	uv run ruff check .

format:
	@echo "Formatting code..."
	uv run ruff format .
	uv run ruff check . --fix

typecheck:
	@echo "Running type checks (ty)..."
	uv run ty check src/

# ------------------------
# TESTING
# ------------------------
test:
	@echo "Running tests..."
	uv run pytest tests/

test-cov:
	@echo "Running tests with coverage..."
	uv run pytest \
		--cov=src \
		--cov-report=term \
		--cov-report=xml:coverage.xml \
		--junitxml=report.xml \
		tests/

# ------------------------
# RUN
# ------------------------
run:
	@echo "Starting FastAPI app..."
	uv run src/main.py

run-prod:
	@echo "Starting production server..."
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

run-worker:
	@echo "Starting worker..."
	uv run python -m src.apps.worker

run-orchestrator:
	@echo "Starting orchestrator..."
	uv run python -m src.apps.orchestrator

# ------------------------
# UTIL
# ------------------------
clean:
	@echo "Removing virtual environment..."
	rm -rf $(VENV_DIR)

reset: clean install