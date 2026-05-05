<!-- refreshed: 2026-05-05 -->
# Architecture

**Analysis Date:** 2026-05-05

## System Overview

```text
┌───────────────────────────────────────────────────────────────────┐
│                        External Data Sources                       │
│   Yahoo Finance (market + fundamentals)   Alpaca Paper Trading    │
└────────────┬──────────────────────────────────────┬───────────────┘
             │                                      │
             ▼                                      ▼
┌─────────────────────────────┐     ┌───────────────────────────────┐
│       Worker Process        │     │        FastAPI Process         │
│  `agentic_trader/worker/`   │     │   `agentic_trader/api/`        │
│                             │     │                               │
│  APScheduler (4 jobs)       │     │  GET /decisions               │
│  scan_job (60 min)          │     │  GET /trades                  │
│  fundamentals_job (60 min)  │     │  (watchlist endpoints         │
│  trade_job (5 min)          │     │   commented out)              │
│  pnl_sync_job (60 min)      │     └──────────────┬────────────────┘
└──────────────┬──────────────┘                    │
               │                                   │
               ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                              │
│  watchlist | agent_votes | decisions | trades                        │
│  `agentic_trader/database/`                                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

| Component | Responsibility | Key File |
|-----------|----------------|----------|
| Worker | Scheduler entrypoint; orchestrates all jobs | `agentic_trader/worker/worker.py` |
| WorkerState | Thread-safe in-memory cache shared between jobs | `agentic_trader/worker/scan_state.py` |
| ScannerEngine | Filters S&P 500 symbols to a top-10 shortlist via RSI+volume score | `agentic_trader/scanner/engine.py` |
| MarketDataEngine | Applies indicator chain to a raw OHLCV DataFrame | `agentic_trader/services/market_data/market_data_engine.py` |
| MultiTimeframeEngine | Runs `MarketDataEngine` on both daily and 4h bars, returns `MultiTimeframeSnapshot` | `agentic_trader/services/market_data/multi_timeframe_engine.py` |
| FeatureBuilder | Extracts scalar features (RSI, trend, volume spike) from a computed DataFrame | `agentic_trader/services/market_data/feature_builder.py` |
| FundamentalsEngine | Fetches `FundamentalsSnapshot` for a list of symbols | `agentic_trader/services/fundamentals/fundamentals_engine.py` |
| BaseAgent | Abstract agent; provides `generate_signal()` template method | `agentic_trader/agents/agent.py` |
| TechnicalAgent | Scores RSI crossovers, MA50 trend, volume on `MultiTimeframeSnapshot` | `agentic_trader/agents/technical/agent.py` |
| FundamentalsAgent | Scores P/E, margin, ROE, D/E, growth vs sector baselines | `agentic_trader/agents/fundamental/agent.py` |
| DiscussionAgent | Aggregates agent votes by weight (technical 0.7, fundamentals 0.3) | `agentic_trader/agents/discussion/agent.py` |
| RiskEngine | Guards trades: confidence floor, cooldown, max position count | `agentic_trader/risk/engine.py` |
| DecisionEngine | Passes `AggregatedResponse` through risk gate, executes order, persists result | `agentic_trader/decision/engine.py` |
| AlpacaController | Thin wrapper around `alpaca-py` TradingClient (paper mode) | `agentic_trader/controller/alpaca_controller.py` |
| TradeRepository | Maps domain objects to SQLAlchemy models; saves decisions, votes, trades | `agentic_trader/database/repository.py` |
| PnlSyncJob | Polls Alpaca FILL activities and back-fills `Trade.pnl` | `agentic_trader/worker/pnl_sync.py` |
| FastAPI app | Read-only REST API over the decisions/trades tables | `agentic_trader/api/app.py` |

## Data Flow

### Scan Job (every 60 minutes)

1. `scan_job()` builds a lightweight pipeline: `YahooFinanceProvider` + `MarketDataEngine(RSI, Volume)` + `FeatureBuilder` → `ScannerEngine` (`agentic_trader/worker/worker.py:93`)
2. `ScannerEngine.scan()` iterates all SYMBOLS (top 10 S&P 500 slice), scores each by RSI extremity + volume, returns top-10 `ScanResult` list (`agentic_trader/scanner/engine.py:15`)
3. Raw daily and 4h bar DataFrames for each top-10 symbol are fetched and stored as `TimeframeData` in `WorkerState._scan` under a threading lock (`agentic_trader/worker/worker.py:107-122`)

### Fundamentals Job (every 60 minutes)

1. `fundamentals_job()` reads `state.symbols` (populated by scan job) (`agentic_trader/worker/worker.py:126`)
2. `FundamentalsEngine.fetch_many()` calls `YahooFundamentalsProvider.get_fundamentals()` per symbol
3. `FundamentalsSnapshot` objects stored in `WorkerState._fundamentals` (TTL 24 h) (`agentic_trader/worker/scan_state.py:63`)

### Trade Job (every 5 minutes)

1. `trade_job()` checks `state.is_market_fresh()` (cache TTL 90 min); skips if stale (`agentic_trader/worker/worker.py:145`)
2. For each symbol in `state.symbols`, calls `_trade_symbol()` inside a DB session
3. **Technical signal:** `MultiTimeframeEngine.compute_from_cache()` reads cached DataFrames, runs full indicator chain, builds `MultiTimeframeSnapshot` → `TechnicalAgent.generate_signal()` → `AgentResponse` (`agentic_trader/worker/worker.py:185`)
4. **Fundamentals signal:** `state.get_fundamentals(symbol)` → `FundamentalsAgent.generate_signal()` → `AgentResponse` (skipped if not cached) (`agentic_trader/worker/worker.py:199`)
5. **Aggregation:** `DiscussionAgent.discuss()` applies weighted scoring (technical 0.7, fundamentals 0.3) → `AggregatedResponse` (`agentic_trader/agents/discussion/agent.py:14`)
6. **Decision + risk:** `DecisionEngine.execute_decision()` persists decision + votes, runs `RiskEngine.can_trade()`, executes BUY/SELL via `AlpacaController` if allowed (`agentic_trader/decision/engine.py:34`)
7. Executed trade is persisted via `database.mapper.to_trade()` and `session.commit()`

### PnL Sync Job (every 60 minutes)

1. `PnlSyncJob.run()` queries `Trade` rows where `pnl IS NULL` (`agentic_trader/worker/pnl_sync.py:54`)
2. Fetches FILL activities from Alpaca REST API (`/v2/account/activities/FILL`)
3. Matches by `order_id`, writes `realized_pl` to `Trade.pnl`, commits

### API Read Path

1. FastAPI receives GET request for `/decisions` or `/trades`
2. SQLAlchemy query over PostgreSQL with optional symbol filter and limit
3. Pydantic schemas serialize the response (`agentic_trader/api/schemas.py`)

## Design Patterns

**Template Method (BaseAgent):**
`BaseAgent.generate_signal()` defines the fixed algorithm skeleton: `_compute_scores()` → `_apply_bias()` → `_decide()` → `_build_response()`. Subclasses (`TechnicalAgent`, `FundamentalsAgent`) only implement `_compute_scores()`. Located in `agentic_trader/agents/agent.py`.

**Provider/Strategy (market data and fundamentals):**
Abstract interfaces `MarketDataProvider` (`agentic_trader/services/market_data/provider.py`) and `FundamentalsProvider` (`agentic_trader/services/fundamentals/provider.py`) decouple engines from concrete implementations. Current providers: `YahooFinanceProvider`, `YahooFundamentalsProvider`, and a partially-implemented `AlpacaProvider`.

**Pipeline / Chain of Responsibility (indicator chain):**
`MarketDataEngine` holds a list of `indicator` objects and applies each in sequence to a DataFrame. Adding a new indicator requires only passing it into the constructor — no existing code changes. Located in `agentic_trader/services/market_data/market_data_engine.py`.

**Repository Pattern:**
`TradeRepository` and `WatchlistRepository` in `agentic_trader/database/repository.py` isolate persistence logic from domain code. The worker calls only repository methods, never SQLAlchemy models directly.

**Mapper / Anti-corruption layer:**
`agentic_trader/database/mapper.py` contains pure factory functions (`to_trade`, `to_decision`, `to_agent_vote`) that translate domain Pydantic models to SQLAlchemy ORM models, keeping the two layers fully decoupled.

**Scheduler-driven worker (cron-style):**
APScheduler `BlockingScheduler` drives the four jobs at fixed intervals. No event queue or message broker is used. The scheduler is configured in `agentic_trader/worker/worker.py:233`.

**Thread-safe shared state:**
`WorkerState` uses a single `threading.Lock` to protect all mutations and reads. Scan, fundamentals, and trade jobs all share the same singleton `state` object instantiated at module level in `agentic_trader/worker/worker.py:50`.

## Key Decisions

**Paper trading only.** `AlpacaController` hardcodes `paper=True` in `agentic_trader/controller/alpaca_controller.py:19`. No live trading path exists.

**Two-process deployment.** The worker (`agentic_trader.worker.worker`) and API (`agentic_trader.api.app`) run as separate Docker containers sharing only the PostgreSQL database. This means the API is purely a read interface over persisted history; it does not control the trading loop.

**In-memory cache with TTL guards.** Market data (90 min TTL) and fundamentals (24 h TTL) are stored in `WorkerState` rather than re-fetched on every trade cycle. This prevents rate-limit exhaustion and decouples the 5-minute trade cadence from data fetch latency.

**Signal weights are hardcoded in the worker.** `DiscussionAgent` weights (`technical: 0.7`, `fundamentals: 0.3`) and agent thresholds are set directly in `agentic_trader/worker/worker.py:80-85`, not in config files or the database.

**Watchlist API is fully commented out.** The `/watchlist` endpoints in `agentic_trader/api/app.py` are present but commented out. The `WatchlistEntry` model and `WatchlistRepository` exist but are not exercised by the running system.

**Risk engine uses in-process cooldown state.** `RiskEngine._last_trade` is a plain dict in memory (`agentic_trader/risk/engine.py:26`). Restarting the worker clears all cooldowns. There is no persistence of cooldown state.

**No migrations tooling wired up.** `create_tables()` calls `Base.metadata.create_all()` directly on startup (`agentic_trader/database/session.py:44`). Alembic is mentioned in a comment but not configured.

## Error Handling

**Strategy:** Per-symbol catch-all in the trade loop. Each symbol processed in `trade_job()` is wrapped in `try/except Exception` with `logger.error(..., exc_info=True)`. Failed symbols are skipped without aborting the cycle (`agentic_trader/worker/worker.py:162`).

**Scan failures:** Individual symbol scan errors are caught with `logger.warning` inside `ScannerEngine.scan()` and do not propagate (`agentic_trader/scanner/engine.py:42`).

**Stale cache guard:** `state.is_market_fresh()` prevents the trade job from firing if market data is older than 90 minutes, providing a circuit-breaker when Yahoo Finance is unavailable.

**Database:** `get_session()` context manager rolls back on any exception and always closes the session (`agentic_trader/database/session.py:31`).

## Architectural Constraints

- **Threading:** Single Python process for the worker; APScheduler runs jobs on the main thread sequentially (BlockingScheduler). `WorkerState` lock guards shared cache but jobs do not run concurrently.
- **Global state:** `state: WorkerState` singleton at module scope in `agentic_trader/worker/worker.py:50`. No other global mutable state.
- **Circular imports:** None detected. The dependency direction is: `worker` → `agents/decision/risk` → `services` → `database`.
- **External rate limits:** Yahoo Finance (`yfinance`) is used for both market data and fundamentals with no explicit rate-limit handling beyond the scan/fundamentals TTL cache design.

---

*Architecture analysis: 2026-05-05*
