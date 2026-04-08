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
run-worker:
	@echo "Starting trading worker..."
	uv run src/worker/trading_loop.py

run-main:
	@echo "Starting main app..."
	uv run src/main.py

# ------------------------
# UTIL
# ------------------------
clean:
	@echo "Removing virtual environment..."
	rm -rf $(VENV_DIR)

reset: clean install