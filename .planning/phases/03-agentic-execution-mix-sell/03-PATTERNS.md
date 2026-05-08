# Phase 03: Agentic Execution (Mix Sell) - Pattern Map

**Mapped:** 2026-05-08
**Status:** Ready for planner use

## Target Files And Closest Analogs

| Target | Role | Closest Existing Analog | Pattern To Reuse |
|--------|------|-------------------------|------------------|
| `agentic_trader/decision/bracket_policy.py` | Deterministic bracket level calculation | `agentic_trader/risk/engine.py` | Small deterministic service with simple constructor defaults and testable methods |
| `agentic_trader/services/market_data/indicators/atr.py` | Market indicator | `agentic_trader/services/market_data/indicators/rsi.py` | Indicator class exposing `compute(df) -> dict` |
| `agentic_trader/services/market_data/response.py` | Snapshot shape | existing `MarketDataSnapshot` | Add typed optional fields; keep Pydantic model simple |
| `agentic_trader/controller/alpaca_controller.py` | Alpaca order integration | existing `place_market_order`, `resolve_tradable_symbol` | Normalize symbol, build SDK request object, submit through `TradingClient`, log/return `None` for untradable symbols |
| `agentic_trader/database/models.py` | Active bracket fields and event model | existing `Trade`, `WorkerHeartbeat` | SQLAlchemy 2.x `Mapped` fields, relationships, `utcnow` timestamps |
| `agentic_trader/database/mapper.py` | ORM mapping | existing `to_trade`, `extract_order_id` | Pure helper functions for Alpaca/domain object -> ORM fields |
| `agentic_trader/database/repository.py` | Persistence operations | existing `TradeRepository` | Session-owned write helpers; no direct SQLAlchemy usage from worker when avoidable |
| `agentic_trader/worker/position_review.py` | Scheduled job object | `agentic_trader/worker/pnl_sync.py`, `agentic_trader/worker/reconciliation.py` | Class with `run()`, logs, opens its own DB session, treats Alpaca as source of truth |
| `agentic_trader/worker/worker.py` | Scheduler integration | existing scan/sentiment/trade/reconciliation jobs | Module-level interval config, explicit warm-up call if safe, scheduler `add_job` |

## Existing Patterns To Preserve

### Controller Boundary

`AlpacaController` is the anti-corruption layer around `alpaca-py`. Phase 03 should add bracket and replacement helpers here instead of constructing SDK requests inside `DecisionEngine` or worker jobs.

### Decision Boundary

`DecisionEngine` should remain the boundary between final aggregated decisions and order execution. Phase 03 should keep it deterministic:
- BUY -> risk quantity -> bracket policy -> `AlpacaController.buy_bracket(...)`
- SELL -> available long quantity -> simple sell/close only

### Worker Job Boundary

Long-running operations belong in explicit jobs:
- scanner jobs prepare candidate context.
- `trade_job` handles entry decisions.
- new position review job handles open-position exit adjustment.

### Persistence Boundary

The repository/mapper layer should own local trade/bracket persistence. New fields should not be set ad hoc throughout worker code.

## Landmines

- `create_all()` will not add missing columns to an existing `trades` table.
- Alpaca replacement returns a new order object and can race with fills.
- A plain SELL order can open a short if quantity guards are bypassed.
- Bracket order child legs may need nested order queries after submission/fill before IDs are visible.
- Market bracket price references must be rounded to Alpaca-accepted increments.

## Pattern Map Complete

Use this map to keep Phase 03 implementation consistent with Phases 01 and 02.

