<!-- refreshed: 2026-05-05 -->
# Structure

**Analysis Date:** 2026-05-05

## Directory Layout

```
agentic-trader/
├── agentic_trader/                  # Main package
│   ├── agents/                      # Signal generation layer
│   │   ├── agent.py                 # BaseAgent abstract class (template method)
│   │   ├── models.py                # AgentResponse, AgentVote, AggregatedResponse (Pydantic)
│   │   ├── discussion/
│   │   │   └── agent.py             # DiscussionAgent — weighted vote aggregation
│   │   ├── fundamental/
│   │   │   └── agent.py             # FundamentalsAgent — sector-relative scoring
│   │   └── technical/
│   │       └── agent.py             # TechnicalAgent — RSI, MA50, volume scoring
│   ├── api/
│   │   ├── app.py                   # FastAPI app: /decisions, /trades endpoints
│   │   └── schemas.py               # Pydantic response/request schemas for API
│   ├── config/
│   │   └── logging.py               # setup_logging() — stdlib logging config
│   ├── controller/
│   │   └── alpaca_controller.py     # Alpaca paper trading client wrapper
│   ├── database/
│   │   ├── mapper.py                # Pure factory functions: Pydantic → SQLAlchemy
│   │   ├── models.py                # SQLAlchemy ORM: WatchlistEntry, AgentVote, Decision, Trade
│   │   ├── repository.py            # TradeRepository, WatchlistRepository
│   │   └── session.py               # Engine, SessionLocal, get_session(), create_tables()
│   ├── decision/
│   │   └── engine.py                # DecisionEngine — risk gate + order execution + persist
│   ├── risk/
│   │   ├── engine.py                # RiskEngine — confidence, cooldown, position count
│   │   └── models.py                # RiskVerdict Pydantic model
│   ├── scanner/
│   │   ├── engine.py                # ScannerEngine — RSI+volume scoring, returns top-N
│   │   └── models.py                # ScanResult Pydantic model
│   ├── services/
│   │   ├── fundamentals/
│   │   │   ├── fundamentals_engine.py  # FundamentalsEngine — fetch_many() over provider
│   │   │   ├── models.py               # FundamentalsSnapshot Pydantic model
│   │   │   ├── provider.py             # Abstract FundamentalsProvider interface
│   │   │   ├── providers/
│   │   │   │   └── yahoo_finance.py    # YahooFundamentalsProvider (yfinance)
│   │   │   └── sector/
│   │   │       └── baselines.py        # get_baseline(sector) — sector P/E, margin, ROE targets
│   │   └── market_data/
│   │       ├── feature_builder.py      # FeatureBuilder — DataFrame → MarketDataSnapshot
│   │       ├── market_data_engine.py   # MarketDataEngine — applies indicator list to DataFrame
│   │       ├── multi_timeframe_engine.py  # MultiTimeframeEngine — daily + 4h snapshot
│   │       ├── provider.py             # Abstract MarketDataProvider interface
│   │       ├── response.py             # MarketDataSnapshot, MultiTimeframeSnapshot (Pydantic)
│   │       ├── indicators/
│   │       │   ├── indicator.py        # Abstract Indicator base class
│   │       │   ├── ma.py               # MovingAverageIndicator (MA50)
│   │       │   ├── rsi.py              # RSIIndicator
│   │       │   └── volume.py           # VolumeIndicator (avg, spike flag)
│   │       └── providers/
│   │           ├── alpaca.py           # AlpacaProvider (partially implemented)
│   │           └── yahoo_finance.py    # YahooFinanceProvider (primary, used in worker)
│   ├── worker/
│   │   ├── models.py                # TimeframeData, ScanSnapshot, FundamentalsCache (Pydantic)
│   │   ├── pnl_sync.py              # PnlSyncJob — syncs Alpaca FILL activities to DB
│   │   ├── scan_state.py            # WorkerState — thread-safe in-memory cache
│   │   └── worker.py                # Entrypoint: APScheduler + 4 jobs
│   ├── data.py                      # sp500_symbols list constant
│   └── main.py                      # Manual Alpaca account/positions inspection script
├── tests/                           # Test directory (currently empty)
├── tmp/                             # Scratch / exploratory scripts
├── .planning/
│   └── codebase/                    # GSD architecture docs (this directory)
├── .ai/                             # AI context/skills directory
├── Dockerfile                       # Single image for both api and worker containers
├── docker-compose.yml               # Three services: db, api, worker
├── pyproject.toml                   # Project metadata, dependencies, ruff, pytest config
├── Makefile                         # Dev workflow shortcuts
├── uv.lock                          # Lockfile (uv package manager)
└── .env.example                     # Required env var template
```

## Key Files

**Worker entrypoint:**
- `agentic_trader/worker/worker.py` — defines all four jobs (`scan_job`, `fundamentals_job`, `trade_job`, `pnl_sync_job`), builds pipelines, runs `BlockingScheduler`. Run via `python -m agentic_trader.worker.worker`.

**API entrypoint:**
- `agentic_trader/api/app.py` — FastAPI application object, lifespan hook (runs `create_tables()`), route handlers for `/decisions` and `/trades`. Run via `uvicorn agentic_trader.api.app:app`.

**Shared state:**
- `agentic_trader/worker/scan_state.py` — `WorkerState` dataclass; all inter-job state lives here.
- `agentic_trader/worker/models.py` — cache model definitions and TTL constants (`CACHE_MAX_AGE = 90 min`, `FUNDAMENTALS_MAX_AGE = 24 h`).

**Domain models (Pydantic):**
- `agentic_trader/agents/models.py` — `AgentResponse`, `AgentVote`, `AggregatedResponse`, `Signal` type alias.
- `agentic_trader/services/market_data/response.py` — `MarketDataSnapshot`, `MultiTimeframeSnapshot`.
- `agentic_trader/services/fundamentals/models.py` — `FundamentalsSnapshot`.
- `agentic_trader/risk/models.py` — `RiskVerdict`.

**Database layer:**
- `agentic_trader/database/models.py` — SQLAlchemy 2.x declarative ORM models.
- `agentic_trader/database/session.py` — engine, `SessionLocal`, `get_session()` context manager.
- `agentic_trader/database/repository.py` — `TradeRepository`, `WatchlistRepository`.
- `agentic_trader/database/mapper.py` — pure factory functions translating domain types to ORM instances.

**Configuration:**
- `pyproject.toml` — all tool config (ruff, pytest, dependencies).
- `docker-compose.yml` — three-container topology (db, api, worker).
- `.env` / `.env.example` — `DATABASE_URL`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`.

## Module Organization

The package is organized into horizontal layers, each with a single clear concern:

| Layer | Modules | Depends On |
|-------|---------|------------|
| Entry / scheduler | `worker/worker.py` | All layers |
| Agents | `agents/` | `services/` models |
| Decision + Risk | `decision/`, `risk/` | `agents/models`, `controller/`, `database/` |
| Services | `services/market_data/`, `services/fundamentals/` | External providers only |
| Controller | `controller/` | `alpaca-py` SDK |
| Database | `database/` | SQLAlchemy, `agents/models` |
| API | `api/` | `database/` only |
| Worker state | `worker/scan_state.py`, `worker/models.py` | `services/` models |

**Providers follow the Abstract-Concrete pattern:**
Each service domain has an abstract `provider.py` (ABC) and concrete providers under `providers/`. This makes swapping data sources straightforward without touching engines or agents.

## Entry Points

**Worker (primary trading loop):**
- Module: `agentic_trader.worker.worker`
- Command: `python -m agentic_trader.worker.worker`
- Docker: `worker` service in `docker-compose.yml`
- What it does: runs all four APScheduler jobs; requires `DATABASE_URL`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` env vars.

**API (read-only HTTP interface):**
- Module: `agentic_trader.api.app`
- Command: `uvicorn agentic_trader.api.app:app --host 0.0.0.0 --port 8000`
- Docker: `api` service in `docker-compose.yml`, exposed on host port 8002
- What it does: serves decision and trade history from PostgreSQL; calls `create_tables()` on startup.

**Manual inspection script (dev only):**
- `agentic_trader/main.py` — prints account status, positions, orders via `AlpacaController`. Not used by any automated system.

## Where to Add New Code

**New agent type:**
- Subclass `BaseAgent` from `agentic_trader/agents/agent.py`
- Implement `_compute_scores(data)` returning `(score_buy, score_sell, reasons_buy, reasons_sell)`
- Place at `agentic_trader/agents/<name>/agent.py`
- Register in `_trade_symbol()` in `agentic_trader/worker/worker.py` and add weight to `DiscussionAgent` constructor call

**New technical indicator:**
- Subclass `Indicator` from `agentic_trader/services/market_data/indicators/indicator.py`
- Place at `agentic_trader/services/market_data/indicators/<name>.py`
- Pass instance to `MarketDataEngine(indicators=[...])` in `build_scan_pipeline()` or `build_trade_pipeline()` in `agentic_trader/worker/worker.py`

**New market data provider:**
- Implement `MarketDataProvider` ABC from `agentic_trader/services/market_data/provider.py`
- Place at `agentic_trader/services/market_data/providers/<name>.py`
- Swap into pipeline factory in `agentic_trader/worker/worker.py`

**New fundamentals provider:**
- Implement `FundamentalsProvider` ABC from `agentic_trader/services/fundamentals/provider.py`
- Place at `agentic_trader/services/fundamentals/providers/<name>.py`

**New API endpoint:**
- Add route handler to `agentic_trader/api/app.py`
- Add Pydantic schema to `agentic_trader/api/schemas.py`
- Inject DB session via `Depends(get_db)`

**New database table:**
- Add SQLAlchemy model to `agentic_trader/database/models.py` (inheriting `Base`)
- Add mapper functions to `agentic_trader/database/mapper.py`
- Add repository class to `agentic_trader/database/repository.py`
- `create_tables()` will pick it up automatically on next startup

**New scheduled job:**
- Implement job function in `agentic_trader/worker/worker.py`
- Register via `scheduler.add_job(fn, "interval", minutes=N)` before `scheduler.start()`

## Special Directories

**`tmp/`:**
- Purpose: scratch scripts and exploratory notebooks
- Generated: No
- Committed: Yes (but not imported by any production module)

**`.planning/codebase/`:**
- Purpose: GSD architecture maps (this document)
- Generated: By GSD mapper agent
- Committed: Yes

**`.venv/`:**
- Purpose: uv-managed virtual environment
- Generated: Yes (`uv sync`)
- Committed: No (in `.gitignore`)

**`tests/`:**
- Purpose: pytest test suite
- Current state: directory exists, no test files present
- Expected location for new tests: `tests/test_<module>.py`

---

*Structure analysis: 2026-05-05*
