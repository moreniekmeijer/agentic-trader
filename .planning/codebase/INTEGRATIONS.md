# Integrations

**Analysis Date:** 2026-05-05

## External APIs & Services

**Alpaca Markets (Paper Trading):**
- Purpose: Order placement, account/position queries, fill activity history
- Endpoint: `https://paper-api.alpaca.markets` (paper mode hardcoded in `AlpacaController.__init__`)
- SDK: `alpaca-py 0.43.2`
- Clients used:
  - `alpaca.trading.client.TradingClient` — orders, positions, account (`agentic_trader/controller/alpaca_controller.py`)
  - `alpaca.data.historical.StockHistoricalDataClient` — historical OHLCV bars (`agentic_trader/services/market_data/providers/alpaca.py`)
  - `alpaca.broker.GetAccountActivitiesRequest` — fill activities (also accessed via direct REST call with `requests` for FILL endpoint)
- Auth env vars: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`
- Note: `paper=True` is hardcoded; switching to live requires code change in `alpaca_controller.py:19`

**Yahoo Finance:**
- Purpose: Market data (OHLCV bars, multi-timeframe) and fundamentals (PE ratio, analyst ratings, sector, etc.)
- SDK: `yfinance 1.2.0` — no API key required
- Market data provider: `agentic_trader/services/market_data/providers/yahoo_finance.py`
- Fundamentals provider: `agentic_trader/services/fundamentals/providers/yahoo_finance.py`
- Data fetched: trailing/forward PE, price-to-book, revenue growth, earnings growth, profit margin, debt-to-equity, ROE, analyst rating, price target, sector, industry
- Note: Yahoo Finance is the primary market data source; Alpaca provider (`alpaca.py`) exists but its `get_bars` method is currently commented out

## Databases & Storage

**PostgreSQL 15:**
- Purpose: Persistent storage for watchlist entries, agent votes, decisions, and trades
- Connection string env var: `DATABASE_URL` (format: `postgresql://user:password@host:5432/agentic_trader`)
- ORM: SQLAlchemy 2.0.49, declarative style with `Mapped`/`mapped_column`
- Adapter: psycopg2-binary 2.9.12
- Session config: `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`
- Session file: `agentic_trader/database/session.py`
- Models file: `agentic_trader/database/models.py`
- Tables:
  - `watchlist` — tracked symbols with thesis/invalidation (`WatchlistEntry`)
  - `agent_votes` — per-agent per-cycle signal votes (`AgentVote`)
  - `decisions` — aggregated trading decisions (`Decision`)
  - `trades` — executed orders linked to Alpaca order IDs and decisions (`Trade`)
- Schema management: `Base.metadata.create_all` at API startup (no Alembic migrations; comment in `session.py` flags this as a future need)
- Docker Compose volume: named volume `postgres_data` persists across restarts

**File Storage:**
- None — no file-based persistence or object storage used

**Caching:**
- In-memory only — `WorkerState` (`agentic_trader/worker/scan_state.py`) holds market data and fundamentals between scheduler cycles with a max cache age (`CACHE_MAX_AGE` from `agentic_trader/worker/models.py`)

## SDKs & Libraries

| Library | Version | Role |
|---------|---------|------|
| `alpaca-py` | 0.43.2 | Alpaca trading + historical data SDK |
| `yfinance` | 1.2.0 | Yahoo Finance market data + fundamentals |
| `SQLAlchemy` | 2.0.49 | ORM and database session management |
| `psycopg2-binary` | 2.9.12 | PostgreSQL driver |
| `FastAPI` | 0.135.3 | REST API framework |
| `uvicorn` | 0.43.0 | ASGI server |
| `APScheduler` | 3.11.2 | Periodic job scheduler (worker) |
| `pydantic` | 2.12.5 | Data validation, API schemas, agent models |
| `pandas` | 3.0.2 | DataFrame operations for market data |
| `numpy` | 2.4.4 | Numerical computation |
| `requests` | 2.33.1 | Direct HTTP to Alpaca FILL activities endpoint |
| `python-dotenv` | 1.2.2 | `.env` file loading |
| `pytz` | 2026.1.post1 | Timezone utilities |

## Environment Configuration

**Required environment variables:**

| Variable | Used In | Purpose |
|----------|---------|---------|
| `ALPACA_API_KEY` | `agentic_trader/controller/alpaca_controller.py`, `agentic_trader/services/market_data/providers/alpaca.py` | Alpaca API authentication |
| `ALPACA_SECRET_KEY` | same as above | Alpaca API secret |
| `DATABASE_URL` | `agentic_trader/database/session.py`, Docker Compose `environment` block | PostgreSQL connection string |
| `ENV_FILE` | `agentic_trader/database/session.py`, `agentic_trader/api/app.py`, `agentic_trader/worker/worker.py`, Docker Compose `env_file` | Path to the active `.env` file (allows switching environments) |

**Env file location:**
- `.env` — actual secrets (not committed, listed in `.gitignore` implied by presence of `.env.example`)
- `.env.example` — template with empty values for `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `DATABASE_URL`

**Loading mechanism:**
- `python-dotenv` `load_dotenv(os.getenv("ENV_FILE"))` called at startup in API lifespan and worker entrypoint
- Docker Compose passes `env_file: ${ENV_FILE}` so the same indirection works in containers

**Webhooks & Callbacks:**
- None — the system polls Alpaca and Yahoo Finance; no incoming webhooks configured

---

*Integration audit: 2026-05-05*
