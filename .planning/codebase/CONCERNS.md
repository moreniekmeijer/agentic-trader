# Codebase Concerns

**Analysis Date:** 2026-05-05

---

## Technical Debt

**No database migrations (Alembic not wired):**
- Issue: Tables are created at startup via `Base.metadata.create_all` in `agentic_trader/api/app.py`. There are no Alembic migration files in the repository. The comment in `agentic_trader/database/session.py:45` says "gebruik Alembic voor productie-migraties" but Alembic is not listed in `pyproject.toml` dependencies and no `alembic/` directory exists.
- Impact: Any schema change requires a manual `drop_tables()` + `create_tables()` cycle in dev, or manual DDL in production. There is even a commented-out `drop_tables()` call left in `agentic_trader/api/app.py:27` that could accidentally wipe all data if uncommented.
- Fix approach: Add Alembic, generate an initial migration from existing `database/models.py`, remove the `create_tables()` startup call.

**Commented-out Trade model columns:**
- Issue: `agentic_trader/database/models.py:143-146` has `closed_at`, `close_price`, and `pnl_pct` commented out of the `Trade` ORM model, but `agentic_trader/database/mapper.py:139-144` references `trade.closed_at`, `trade.close_price`, and `trade.pnl_pct` in `close_trade()`. The API schema `agentic_trader/api/schemas.py:67-68` also exposes `closed_at`, `close_price`, and `pnl_pct` as response fields. The `GET /trades` endpoint at `agentic_trader/api/app.py:189-190` accesses `t.closed_at` and `t.pnl_pct` directly.
- Impact: Runtime `AttributeError` when `close_trade()` or the trades endpoint is invoked. The PnL tracking feature is partially broken.
- Fix approach: Uncomment the columns in `database/models.py`, add an Alembic migration to add the columns to the database.

**`RiskEngine.register_trade()` is never called:**
- Issue: `agentic_trader/risk/engine.py:54` defines `register_trade()` which records the timestamp for cooldown enforcement. The `DecisionEngine` in `agentic_trader/decision/engine.py` executes trades but never calls `risk_engine.register_trade()`.
- Impact: The per-symbol cooldown check in `_in_cooldown()` never activates. The system can submit multiple orders for the same symbol within the 10-minute cooldown window.
- Fix approach: Call `self.risk.register_trade(response.symbol)` in `DecisionEngine._persist_trade()` after a successful trade execution.

**`PnlSyncJob._fetch_activities()` makes two API calls:**
- Issue: `agentic_trader/worker/pnl_sync.py:63-66` calls `self.alpaca.get_fill_activities()` twice — once to log the sample and once as the return value.
- Impact: Double the API calls to Alpaca per sync cycle, wasting rate limit quota.
- Fix: Assign to a variable, log from it, and return that variable.

**`main.py` is a dead script:**
- Issue: `agentic_trader/main.py` is an ad-hoc smoke-test script that prints directly to stdout using `print()`. It has no relation to the actual worker or API entrypoint.
- Impact: Misleading for new contributors who expect `main.py` to be the application entrypoint. The actual entrypoints are `agentic_trader/worker/worker.py` and `agentic_trader/api/app.py`.
- Fix approach: Remove or rename it to `scripts/smoke_test.py`, or add a clear module docstring clarifying its purpose.

**`tmp/` directory committed to source control:**
- Issue: `tmp/script_decision_engine.py` is a development scratch script using stale import paths (`from providers.market_data...`) that no longer match the package structure. The `tmp/` directory itself has `__pycache__` present.
- Impact: Confusing to contributors; stale import paths would cause `ImportError` if executed.
- Fix approach: Add `tmp/` to `.gitignore` and remove committed files.

**`data.py` contains duplicate symbols:**
- Issue: `agentic_trader/data.py` lists `"MOS"` twice (lines 128 and 269) and `"JKHY"` twice (lines 128 area and 359), and `"QRVO"` twice (lines 279 and 357).
- Impact: The scanner processes duplicate symbols, wasting API calls to Yahoo Finance; the scanner shortlist could surface the same symbol twice.
- Fix approach: Convert to a `set` or deduplicate the list; add a runtime assert checking `len(sp500_symbols) == len(set(sp500_symbols))`.

**Scanner score conflates buy and sell signals:**
- Issue: `agentic_trader/scanner/engine.py:49-63` scores RSI extremes (both oversold and overbought) with the same positive score. A stock with RSI > 70 scores higher and ranks better than a neutral stock.
- Impact: The scanner shortlist may surface stocks that are overbought — immediately causing `SELL` signals in the trade loop — rather than stocks ripe for a BUY. The scan result is used for both buy and sell candidate selection indiscriminately.
- Fix approach: Separate scan modes (buy-candidates vs sell-candidates) or score RSI differently for each direction.

---

## Security Risks

**Hardcoded credentials in `docker-compose.yml`:**
- Risk: `docker-compose.yml:9-10` hardcodes `POSTGRES_USER: trader` and `POSTGRES_PASSWORD: trader` in plaintext. The `DATABASE_URL` in the `api` and `worker` services also embeds these credentials inline.
- Files: `docker-compose.yml:9-10`, `docker-compose.yml:21`, `docker-compose.yml:34`
- Current mitigation: This is marked as a development setup; the Postgres port is exposed only on 5433.
- Recommendation: Move database credentials to the `.env` file and use `${POSTGRES_PASSWORD}` substitution; never commit default credentials to source control.

**API has no authentication:**
- Risk: The FastAPI app in `agentic_trader/api/app.py` exposes `GET /decisions`, `GET /trades`, and (when uncommented) watchlist mutation endpoints with no authentication or authorization layer.
- Files: `agentic_trader/api/app.py:132-196`
- Current mitigation: None. Access control relies entirely on network-level controls (not running it publicly).
- Recommendation: Add at minimum an API key header check or HTTP Basic Auth using FastAPI's dependency injection before any endpoint that reads or writes trade data.

**`AlpacaController` uses `print()` for errors instead of structured logging:**
- Risk: `agentic_trader/controller/alpaca_controller.py:35,46,59,74,93` uses `print()` for all error output. In a containerized environment, these will mix with structured log output and may be lost or cause log-injection confusion.
- Files: `agentic_trader/controller/alpaca_controller.py`
- Recommendation: Replace all `print()` calls with `logger.error()` or `logger.warning()` using the module-level logger.

**`paper=True` is hardcoded:**
- Risk: `agentic_trader/controller/alpaca_controller.py:19` hardcodes `paper=True` in the `TradingClient` instantiation. If this line is edited (e.g., to enable live trading) without changing configuration management, the system immediately trades with real money.
- Recommendation: Derive `paper` mode from an environment variable (e.g., `ALPACA_PAPER=true`) and validate it explicitly at startup.

**`get_fill_activities()` uses raw HTTP instead of the Alpaca SDK:**
- Risk: `agentic_trader/controller/alpaca_controller.py:65-75` sends raw `requests.get` to the hardcoded paper URL `https://paper-api.alpaca.markets/v2/account/activities/FILL` while the rest of the controller uses the official `alpaca-py` SDK.
- Files: `agentic_trader/controller/alpaca_controller.py:65`
- Risk: The hardcoded paper URL means PnL sync silently fetches nothing if the system is ever switched to live trading. The API secret is also passed in plain HTTP headers manually.
- Recommendation: Use the SDK's `BrokerClient` (imported but unused: `agentic_trader/controller/alpaca_controller.py:5`) or the SDK's activity endpoint instead of a raw request.

---

## Scalability Concerns

**In-memory `WorkerState` is not shared across processes:**
- Problem: `agentic_trader/worker/scan_state.py` uses a `threading.Lock`-protected in-memory `WorkerState`. The API (`api/app.py`) and worker (`worker/worker.py`) run as separate Docker containers and do not share this state.
- Files: `agentic_trader/worker/scan_state.py`, `agentic_trader/worker/worker.py:50`
- Impact: The API has no visibility into what the worker's current shortlist or scan state is. There is no way to query "which symbols are currently being traded" via the API.
- Scaling path: Persist scan state to the database or a shared cache (Redis), and expose it via an API endpoint.

**Sequential per-symbol processing in `scan_job` and `trade_job`:**
- Problem: `agentic_trader/worker/worker.py:108-120` and `157-163` iterate symbols sequentially. Each iteration makes blocking HTTP calls to Yahoo Finance and Alpaca. With 10 symbols at 5-minute intervals this is manageable, but the `data.py` list has ~360 symbols that are scanned one by one.
- Files: `agentic_trader/worker/worker.py:93-123`, `agentic_trader/worker/worker.py:145-163`
- Impact: A slow Yahoo Finance response for one symbol blocks all subsequent symbols in the same cycle. Scan cycles with 10+ symbols risk exceeding the 60-minute `SCAN_INTERVAL`.
- Scaling path: Use `concurrent.futures.ThreadPoolExecutor` for the scan loop; Yahoo Finance does not enforce strict per-IP rate limits on `yfinance`.

**`RiskEngine._last_trade` is in-memory only:**
- Problem: `agentic_trader/risk/engine.py:25` stores the cooldown map in a plain Python dict. A worker restart resets all cooldowns.
- Files: `agentic_trader/risk/engine.py`
- Impact: After a restart the risk engine allows immediate re-trading of any symbol regardless of the configured 10-minute cooldown.
- Scaling path: Persist last-trade timestamps to the database (the `trades` table already has timestamps) and reload them at startup.

**`AlpacaController.get_positions()` is called redundantly inside a loop:**
- Problem: `agentic_trader/risk/engine.py:41` calls `self.alpaca.get_positions()` on every `can_trade()` call, which is called once per symbol in the trade loop. With 10 symbols this is 10 API calls to Alpaca per trading cycle to retrieve the same position list.
- Files: `agentic_trader/risk/engine.py:41`, `agentic_trader/worker/worker.py:157-163`
- Scaling path: Fetch positions once per trade cycle in `trade_job()` and pass them to `RiskEngine`.

---

## Missing Pieces

**No tests exist:**
- Problem: The `tests/` directory is empty. `pyproject.toml` configures pytest with `testpaths = ["tests"]` and `pytest` is listed as a dev dependency. The `.pytest_cache` directory exists, indicating pytest has been run, but there are zero test files.
- Files: `tests/` (empty), `pyproject.toml:47-49`
- Risk: Every module — agents, risk engine, decision engine, scanner scoring, fundamentals scoring, database mapper — is untested. Regressions from any change are undetectable automatically.
- Priority: High. Core scoring logic (`agents/fundamental/agent.py`, `agents/technical/agent.py`, `decision/engine.py`, `risk/engine.py`) is the highest priority.

**No Alembic migrations:**
- Problem: See Technical Debt section. The project has no migration history. Schema changes require manual intervention.
- Files: No `alembic/` directory, no `alembic.ini`.

**Watchlist API endpoints are fully commented out:**
- Problem: `agentic_trader/api/app.py:64-124` has all three watchlist endpoints (`GET /watchlist`, `POST /watchlist`, `DELETE /watchlist/{symbol}`) commented out. The `WatchlistRepository` and `WatchlistEntry` model are fully implemented but inaccessible.
- Files: `agentic_trader/api/app.py:64-124`
- Impact: Watchlist management requires direct database access. There is no way to add or remove symbols from the watchlist programmatically.

**Agent performance analysis endpoint is commented out:**
- Problem: `agentic_trader/api/app.py:204-228` has the `GET /analysis/agent-performance` endpoint commented out. `AgentPerformanceResponse` schema exists but is unused.
- Files: `agentic_trader/api/app.py:204-228`, `agentic_trader/api/schemas.py:72-78`
- Impact: There is no way to evaluate which agents are performing well or poorly. Post-trade analysis requires manual SQL queries.

**No stop-loss or position exit strategy:**
- Problem: The `RiskEngine` only checks entry conditions (max positions, confidence, cooldown). There is no logic to close positions that have fallen below a loss threshold or have been held past a time limit.
- Files: `agentic_trader/risk/engine.py`, `agentic_trader/decision/engine.py`
- Impact: Losing positions are held indefinitely unless the SELL signal happens to trigger on a subsequent scan cycle. This is a meaningful financial risk for a live trading system.

**`AlpacaController.get_orders()` uses no filter:**
- Problem: `agentic_trader/controller/alpaca_controller.py:77-78` calls `self.client.get_orders()` with no query parameters, returning all orders (potentially hundreds of historical orders). The `has_open_orders()` method then iterates this full list for every symbol check.
- Files: `agentic_trader/controller/alpaca_controller.py:49-60`, `agentic_trader/controller/alpaca_controller.py:77-78`
- Fix: Pass `GetOrdersRequest(status=QueryOrderStatus.OPEN)` to filter server-side.

**Sector baselines are static and hardcoded:**
- Problem: `agentic_trader/services/fundamentals/sector/baselines.py` contains 5 hardcoded sectors with manually set P/E, D/E, margin, and ROE baselines. Many S&P 500 sectors are missing (Energy, Industrials, Real Estate, Communication Services, Consumer Defensive, Basic Materials).
- Files: `agentic_trader/services/fundamentals/sector/baselines.py`
- Impact: Stocks from missing sectors fall back to `DEFAULT_BASELINE` which may significantly misrepresent their sector norms and produce biased scoring.

**`pyproject.toml` has `pythonpath = ["src"]` pointing to non-existent directory:**
- Problem: `pyproject.toml:49` sets `pythonpath = ["src"]` for pytest, but the project uses `agentic_trader/` as the package root — there is no `src/` directory.
- Files: `pyproject.toml:49`
- Impact: If tests import from `src.*` they will fail with `ModuleNotFoundError`. This suggests the test configuration was never actually exercised.

---

## Known TODOs & Issues

**Duplicate `Signal` type alias defined in multiple modules:**
- `Signal = Literal["BUY", "SELL", "HOLD"]` is defined in `agentic_trader/agents/models.py:5`, `agentic_trader/agents/agent.py:6`, `agentic_trader/agents/fundamental/agent.py:10`, and `agentic_trader/agents/technical/agent.py:9`. The canonical definition is in `agents/models.py` but submodules redefine it locally instead of importing from the canonical location.

**`get_session()` in `pnl_sync.py` double-commits on success path:**
- `agentic_trader/worker/pnl_sync.py:51` calls `session.commit()` explicitly inside the `run()` method, but `agentic_trader/database/session.py:36` also auto-commits on clean `yield` exit. This causes a harmless but redundant commit. If the session raises between the explicit commit and the context manager's commit, the rollback in the finally block runs on an already-committed session.

**`TradeRepository.mark_executed()` is defined but not used:**
- `agentic_trader/database/repository.py:50-71` defines `mark_executed()` but `agentic_trader/decision/engine.py` uses `database/mapper.py` helpers directly (`to_trade`, `mark_decision_executed`) instead. The `mark_executed()` method in `TradeRepository` is dead code.

**`SYMBOLS = sp500_symbols[:10]` limits trading to 10 symbols:**
- `agentic_trader/worker/worker.py:40` hardcodes the scan universe to the first 10 symbols from `data.py`. This is not driven by a configuration value or environment variable, meaning expanding the scan universe requires a code change.

**Dutch comments mixed with English code:**
- Multiple files contain Dutch-language comments and docstrings: `agentic_trader/database/session.py`, `agentic_trader/database/models.py`, `agentic_trader/database/repository.py`, `agentic_trader/worker/pnl_sync.py`. This creates inconsistency and is a barrier for non-Dutch contributors.

---

## Recommendations

**Priority 1 — Fix silent runtime errors:**
1. Uncomment `closed_at`, `close_price`, `pnl_pct` columns in `agentic_trader/database/models.py:143-146` and add them to the database schema.
2. Call `self.risk.register_trade(response.symbol)` in `agentic_trader/decision/engine.py` after a successful trade to activate cooldown enforcement.
3. Fix `agentic_trader/worker/pnl_sync.py:63-66` — assign `get_fill_activities()` to a variable and return it rather than calling it twice.

**Priority 2 — Test coverage:**
1. Write unit tests for `agentic_trader/agents/fundamental/agent.py` `_compute_scores` with known fixture data.
2. Write unit tests for `agentic_trader/risk/engine.py` covering the confidence, cooldown, and position-count checks.
3. Write unit tests for `agentic_trader/decision/engine.py` with mocked `AlpacaController` and `RiskEngine`.
4. Fix `pyproject.toml:49` — change `pythonpath = ["src"]` to `pythonpath = ["."]` or remove it.

**Priority 3 — Security hardening:**
1. Add authentication (API key or JWT) to all FastAPI endpoints in `agentic_trader/api/app.py`.
2. Move Postgres credentials out of `docker-compose.yml` into environment variable references.
3. Replace the raw `requests.get` in `agentic_trader/controller/alpaca_controller.py:65` with the Alpaca SDK.
4. Derive `paper=True/False` from an environment variable in `agentic_trader/controller/alpaca_controller.py:19`.
5. Replace all `print()` calls in `agentic_trader/controller/alpaca_controller.py` with structured logging.

**Priority 4 — Reliability and completeness:**
1. Set up Alembic and replace the startup `create_tables()` call with proper migrations.
2. Uncomment and restore the watchlist API endpoints in `agentic_trader/api/app.py`.
3. Add server-side order status filtering in `agentic_trader/controller/alpaca_controller.py:77`.
4. Add missing sector baselines (Energy, Industrials, Real Estate, etc.) in `agentic_trader/services/fundamentals/sector/baselines.py`.
5. Add stop-loss logic to `agentic_trader/risk/engine.py` or `agentic_trader/decision/engine.py`.
6. Deduplicate `agentic_trader/data.py` and make `SYMBOLS` count configurable via environment variable.
7. Remove or gitignore the `tmp/` directory.

---

*Concerns audit: 2026-05-05*
