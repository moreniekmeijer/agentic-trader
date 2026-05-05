# Stack

**Analysis Date:** 2026-05-05

## Languages

**Primary:**
- Python 3.11 — all application code; minimum `>=3.11` enforced in `pyproject.toml`, Docker image pins `python:3.11-slim`

**Type Annotations:**
- Full use of `from __future__ import annotations` + PEP 604 union syntax (`X | Y`) throughout source files

## Frameworks & Libraries

**Web / API:**
- FastAPI 0.135.3 — REST API server (`agentic_trader/api/app.py`), lifespan-based startup
- Starlette 1.0.0 — underlying ASGI layer used by FastAPI
- Uvicorn 0.43.0 — ASGI server, run via `uv run uvicorn ... --host 0.0.0.0 --port 8000`

**Scheduling:**
- APScheduler 3.11.2 — `BlockingScheduler` drives the worker loop (`agentic_trader/worker/worker.py`); intervals: scan 60 min, trade 5 min, fundamentals 60 min, PnL sync 60 min

**Data / ORM:**
- SQLAlchemy 2.0.49 — declarative ORM with `Mapped`/`mapped_column` style (`agentic_trader/database/models.py`)
- psycopg2-binary 2.9.12 — PostgreSQL adapter
- Pydantic 2.12.5 — data validation and API schemas (`agentic_trader/api/schemas.py`, agent models)

**Market Data & Finance:**
- alpaca-py 0.43.2 — Alpaca trading API SDK; used for order placement, account/position queries, fill activities (`agentic_trader/controller/alpaca_controller.py`, `agentic_trader/services/market_data/providers/alpaca.py`)
- yfinance 1.2.0 — Yahoo Finance data; used as primary market data and fundamentals provider (`agentic_trader/services/market_data/providers/yahoo_finance.py`, `agentic_trader/services/fundamentals/providers/yahoo_finance.py`)
- pandas 3.0.2 — OHLCV DataFrames, technical indicator computation
- numpy 2.4.4 — underlying numerical operations

**Utilities:**
- python-dotenv 1.2.2 — loads `.env` / `ENV_FILE`-pointed env files at startup
- pytz 2026.1.post1 — timezone handling
- requests 2.33.1 — direct HTTP calls to Alpaca REST (fill activities endpoint in `alpaca_controller.py`)

## Runtime & Build

**Runtime:**
- Python 3.11 (CPython), confirmed by Dockerfile `FROM python:3.11-slim`

**Package Manager:**
- `uv` (installed via `pip install uv` in Docker); lockfile `uv.lock` present and committed
- All commands run as `uv run <cmd>` — no virtual env activation needed in CI/Docker

**Linting & Formatting:**
- Ruff 0.15.9 — linting (`E`, `F`, `I` rule sets) and formatting (double quotes, line-length 110)
- Config in `pyproject.toml` under `[tool.ruff]`

**Type Checking:**
- ty 0.0.28 — Astral's type checker, run via `uv run ty check .`
- Config target: `py311`

**Testing:**
- pytest 9.0.2 — test runner, `testpaths = ["tests"]`, `pythonpath = ["src"]`
- pytest-cov 7.1.0 — coverage reporting; XML + terminal output via `make test-cov`

**Task Runner:**
- `Makefile` — canonical entrypoint for `install`, `format`, `lint`, `typecheck`, `test`, `run-api`, `run-worker`, `run-main`, `clean`, `reset`

## Package Management

- `uv` with `pyproject.toml` (PEP 517/518) and `uv.lock` lockfile
- No `requirements.txt` — `uv sync` is the install command
- Dev dependencies in `[dependency-groups] dev` section

## Deployment & Infrastructure

**Containerisation:**
- Docker — `Dockerfile` builds from `python:3.11-slim`, installs `gcc`, installs `uv`, then runs `uv sync`
- Docker Compose (`docker-compose.yml`) — three services:
  - `db`: `postgres:15`, port `5433:5432`, named volume `postgres_data`
  - `api`: built image, port `8002:8000`, runs uvicorn
  - `worker`: built image, no port exposed, runs `python -m agentic_trader.worker.worker`
- Environment loaded via `env_file: ${ENV_FILE}` in Compose

**Database:**
- PostgreSQL 15 (Docker Compose `postgres:15` image)
- Tables created at API startup via `Base.metadata.create_all` (no Alembic migrations in place yet — noted in `session.py` comment)
- Connection pool: `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`

**Ports:**
- API: `8002` (host) → `8000` (container)
- PostgreSQL: `5433` (host) → `5432` (container)

---

*Stack analysis: 2026-05-05*
