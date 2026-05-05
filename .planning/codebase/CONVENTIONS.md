# Coding Conventions

**Analysis Date:** 2026-05-05

## Code Style

**Formatter:** Ruff (`uv run ruff format .`)
- Line length: 110 characters (set in `pyproject.toml`)
- Quote style: double quotes
- Target Python version: 3.11+

**Linter:** Ruff (`uv run ruff check .`)
- Rule sets: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort)
- Auto-fix available: `uv run ruff check . --fix`

**Type checker:** `ty` (`uv run ty check .`)
- Configured via `pyproject.toml` `[tool.ruff]` block
- No strict mode enforced; type annotations present throughout but not exhaustive

**Run all quality checks:**
```bash
make format    # ruff format + ruff check --fix
make lint      # ruff check
make typecheck # ty check
make all       # format + lint + typecheck + test
```

## Naming Conventions

**Files:**
- `snake_case.py` for all modules (e.g., `market_data_engine.py`, `alpaca_controller.py`, `feature_builder.py`)
- `models.py` for Pydantic/SQLAlchemy model definitions in each subdirectory
- `agent.py` for the agent implementation inside each agent subdirectory

**Classes:**
- `PascalCase` throughout
- Engine classes: `ScannerEngine`, `MarketDataEngine`, `DecisionEngine`, `RiskEngine`, `FundamentalsEngine`
- Agent classes: `BaseAgent`, `TechnicalAgent`, `FundamentalsAgent`, `DiscussionAgent`
- Repository classes: `TradeRepository`, `WatchlistRepository`
- Provider classes: `YahooFinanceProvider`, `YahooFundamentalsProvider`, `AlpacaController`
- Pydantic models: `AgentResponse`, `AgentVote`, `RiskVerdict`, `MarketDataSnapshot`, `FundamentalsSnapshot`
- SQLAlchemy models: `Decision`, `Trade`, `AgentVote` (same as Pydantic in `agents/models.py` — no name collision because they live in separate modules)

**Functions and methods:**
- `snake_case` for all functions and methods
- Private methods prefixed with a single underscore: `_compute_scores`, `_apply_bias`, `_decide`, `_clamp`, `_build_response`, `_score`, `_in_cooldown`
- Public interface methods: `generate_signal`, `discuss`, `execute_decision`, `scan`, `compute`, `fetch`, `fetch_many`

**Variables:**
- `snake_case` for local variables and instance attributes
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `SCAN_INTERVAL`, `TRADE_INTERVAL`, `CACHE_MAX_AGE`, `_WEIGHTS`)
- Type aliases: `PascalCase` or `CamelCase` (e.g., `Signal`, `Trend`, `RsiTrend`, `AnalystRating`)

**Type literals (domain enums):**
- Expressed as `Literal["BUY", "SELL", "HOLD"]` type aliases, not Python `Enum` classes
- `Signal = Literal["BUY", "SELL", "HOLD"]` — defined in `agentic_trader/agents/agent.py` and `agentic_trader/agents/models.py`
- `Trend = Literal["BULLISH", "BEARISH"]` — defined in `agentic_trader/services/market_data/response.py`
- `RsiTrend = Literal["UP", "DOWN"]` — defined in `agentic_trader/services/market_data/response.py`

## File Organization

**Package layout:**
```
agentic_trader/
├── agents/               # Signal-generating agents + base + shared models
│   ├── agent.py          # BaseAgent ABC
│   ├── models.py         # AgentResponse, AgentVote, AggregatedResponse
│   ├── discussion/agent.py
│   ├── fundamental/agent.py
│   └── technical/agent.py
├── api/                  # FastAPI app + Pydantic request/response schemas
│   ├── app.py
│   └── schemas.py
├── config/               # Cross-cutting config (logging only so far)
│   └── logging.py
├── controller/           # External broker adapters
│   └── alpaca_controller.py
├── database/             # SQLAlchemy models, session, repository, mapper
│   ├── mapper.py
│   ├── models.py
│   ├── repository.py
│   └── session.py
├── decision/             # Orchestrates risk check + trade execution
│   └── engine.py
├── risk/                 # Risk rules + verdict model
│   ├── engine.py
│   └── models.py
├── scanner/              # Symbol scoring/shortlisting
│   ├── engine.py
│   └── models.py
├── services/             # Domain services (market data, fundamentals)
│   ├── fundamentals/
│   └── market_data/
├── worker/               # APScheduler-based background job runner
│   ├── models.py
│   ├── pnl_sync.py
│   ├── scan_state.py
│   └── worker.py
├── data.py               # Static data (S&P 500 symbol list)
└── main.py               # Ad-hoc CLI entry point
```

**Sub-package convention:**
- Each major agent has its own subdirectory with `__init__.py` + `agent.py`
- Each service subdirectory has `models.py` for data types, `provider.py` for the abstract interface, and `providers/` for concrete implementations
- Database layer split into four files: `models.py` (ORM), `session.py` (connection), `repository.py` (write operations), `mapper.py` (domain → ORM translation functions)

**Module-level `__init__.py`:**
- Present everywhere but kept empty (no re-exports)

## Linting & Formatting

**Tool:** Ruff (combines formatting and linting in one binary)
**Config location:** `pyproject.toml` under `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]`

```toml
[tool.ruff]
line-length = 110
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = []

[tool.ruff.format]
quote-style = "double"
```

**Import ordering:** Enforced by Ruff's `I` ruleset (isort-compatible):
1. Standard library imports
2. Third-party imports (fastapi, sqlalchemy, pydantic, pandas, alpaca_trade_api, etc.)
3. First-party imports (`agentic_trader.*`)

**`from __future__ import annotations`:**
- Used in files with forward references to SQLAlchemy models (`database/models.py`, `database/repository.py`, `database/mapper.py`, `database/session.py`, `decision/engine.py`, `agents/discussion/agent.py`)

## Documentation Standards

**Module docstrings:**
- Used sparingly; present on `database/models.py`, `database/session.py`, `database/repository.py` to explain schema/connection details
- Not required for agent or service modules

**Class docstrings:**
- Used on SQLAlchemy model classes to describe business purpose (e.g., `WatchlistEntry`, `Decision`, `Trade`)
- Not used on Pydantic models or engine classes

**Method docstrings:**
- Used only on non-obvious methods with nuanced behavior
- Examples: `_score_relative`, `_score_pe`, `_score_growth` in `agentic_trader/agents/fundamental/agent.py`
- Format: plain text description of what the method returns, with a `Returns:` note when multiple values are returned
- No Sphinx-style `:param:` or `:returns:` annotations used anywhere

**Inline comments:**
- Section dividers use `# ---...---` separator lines (dash-based, not `#` + `=`)
- Domain context notes are written as short inline comments after assignments (e.g., `# "buy" | "sell"`, `# risk engine reden`)
- Mixed Dutch/English: database model docstrings and inline comments are in Dutch; all code identifiers and logic comments are in English

**Logging:**
- Module-level logger per file: `logger = logging.getLogger(__name__)`
- Used in every module that has side effects (engines, repositories, worker)
- Not used in pure data/model files
- Format configured centrally in `agentic_trader/config/logging.py`: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Log levels used: `logger.info` for state changes and trade events, `logger.warning` for skipped/failed operations, `logger.debug` for verbose diagnostic output, `logger.error(..., exc_info=True)` for unexpected exceptions in the worker loop

---

*Convention analysis: 2026-05-05*
