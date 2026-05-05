# Agentic Trader — Agent instructions (concise)

This file gives targeted, actionable guidance for AI coding assistants working in this repository. Keep edits short and concrete — reference the specific files listed below when changing behavior.

1. Big-picture architecture (what to touch and why)

- Entry points:
  - `agentic_trader/main.py` — simple script used for quick Alpaca smoke tests.
  - `agentic_trader/api/app.py` — FastAPI app and DB lifecycle (create_tables() on startup in dev).
  - `agentic_trader/worker/worker.py` — The core trading loop/scheduler (Scanner -> Fundamentals -> Decision).
- Major subsystems (boundaries):
  - agents/ — individual agent implementations inherit `BaseAgent` (`agents/agent.py`) and return `AgentResponse`/`AggregatedResponse` (`agents/models.py`). AI changes to agent logic should preserve the response shape.
  - services/market_data & services/fundamentals — providers (Yahoo, Alpaca) and engines that compute indicators (`services/market_data/market_data_engine.py`, `services/fundamentals/fundamentals_engine.py`). Prefer adding new providers via the existing Provider base-classes.
  - controller/ — external broker API wrapper (`controller/alpaca_controller.py`) used by decision engine; treat as thin orchestration layer.
  - decision/ & risk/ — orchestration: `decision/engine.py` persists decisions via `database/repository.py` and asks `risk/engine.py` for trade permission. Keep orchestration logic explicit and side-effectful (DB writes, Alpaca calls) in these modules.

2. Data flows and contracts (concrete shapes)

- Agent -> Aggregator -> DecisionEngine:
  - Agents produce `AgentResponse` (see `agents/models.py`). Aggregated results use `AggregatedResponse` with `votes: list[AgentVote]`.
  - DecisionEngine expects AggregatedResponse and persists via `database/mapper.py` / `database/repository.py`.
- DB mapping helpers live in `database/mapper.py` (e.g. `to_trade`, `to_decision`, `mark_decision_executed`). Prefer using these helpers when constructing model instances.

3. Project-specific conventions and patterns

- Naming: classes named \*Agent typically map to an agent id (class name without `Agent`, lowercased) — see `BaseAgent._build_response` in `agents/agent.py`.
- Uppercasing symbols: many helpers call `symbol.upper()` before persisting — preserve this for any new code that stores symbols (see `database/mapper.py`, `repository.py`).
- Providers: implement Provider subclasses under `services/*/providers/` and pass into Engines (e.g., `YahooFinanceProvider` under `services/market_data/providers`). Follow existing method names (`get_bars`, `get_fundamentals`).
- Orchestration vs side-effects: keep pure computations (indicator math, scoring) in services/ or agents/; keep side-effects (DB, API calls) in controller/, database/, or decision/engine.py. This separation is relied on by tests and code structure.

4. Integration points & external deps (what to watch for)

- Alpaca: wrapped by `controller/alpaca_controller.py`. Alpaca API keys are read via `dotenv` from a file path specified by the `ENV_FILE` environment variable.
- Market data & fundamentals: `yfinance` is used (`services/*/providers/yahoo_finance.py`). Expect flaky network responses and occasionally missing keys in `yf.Ticker(...).info` — code already uses `_safe_float` and parsing guards.
- Database: SQLAlchemy engine is built from `DATABASE_URL` in `.env` (see `database/session.py`). For local dev the app creates tables automatically (`create_tables()` in `api/app.py`). Production migrations are expected to be handled externally (Alembic) — do not add ad-hoc schema drops.

5. Developer workflows & useful commands

- Install & run (recommended): project uses Python >=3.11 and `uv`.
  - Install deps: `uv sync`
  - Run API: `make run-api` (Port 8000 default, or specify `--port` as we did for 8002)
  - Run Worker: `make run-worker`
  - Docker: `docker-compose up -d --build` (API on 8002 by default in config)
  - Quick Alpaca smoke: `make run-main` (Requires `ENV_FILE` env var)
- Tests: pytest is configured. Run tests with `pytest` (tests/ directory exists). Keep tests small and avoid touching live Alpaca or network by mocking providers.

6. Useful file references and examples (copy-as-needed)

- Agent interface and scoring: `agentic_trader/agents/agent.py` (look for \_compute_scores, generate_signal)
- Aggregated data model: `agentic_trader/agents/models.py`
- Decision orchestration: `agentic_trader/decision/engine.py` (risk checks, call into `controller/alpaca_controller.py`, persist via `database/repository.py`)
- DB session helpers: `agentic_trader/database/session.py` (create_tables(), get_session())
- DB mapper helpers: `agentic_trader/database/mapper.py` (to_trade, to_decision)

7. Quick editing rules for AI agents

- Preserve symbols uppercasing and AgentResponse shapes.
- Add new providers under services/\*/providers and wire them into engines rather than altering engines' public API.
- When changing persistence, prefer using mapper helpers and repositories to keep a single place for DB logic.
- Avoid committing secrets or .env files. Use env var names above for reference only.

If anything is unclear or you want me to expand a section (examples of tests, CI steps, or a short dev README), tell me which area and I will iterate.
