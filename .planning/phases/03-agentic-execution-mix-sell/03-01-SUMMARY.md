---
phase: 03-agentic-execution-mix-sell
plan: 01
subsystem: execution
tags: [alpaca, bracket-orders, risk, persistence, atr]
requires:
  - phase: 02-multi-stage-scanner
    provides: enriched candidate market context
provides:
  - ATR-enhanced trade market snapshots
  - deterministic bracket price policy
  - Alpaca bracket BUY submission
  - parent/child bracket leg persistence
  - bracket submission event audit trail
affects: [phase-03-execution, phase-04-learning, worker, decision-engine, database]
key-files:
  created:
    - agentic_trader/decision/bracket_policy.py
    - agentic_trader/services/market_data/indicators/atr.py
    - tests/test_alpaca_bracket_orders.py
    - tests/test_bracket_policy.py
  modified:
    - agentic_trader/controller/alpaca_controller.py
    - agentic_trader/database/mapper.py
    - agentic_trader/database/models.py
    - agentic_trader/database/repository.py
    - agentic_trader/database/session.py
    - agentic_trader/decision/engine.py
    - agentic_trader/services/market_data/feature_builder.py
    - agentic_trader/services/market_data/response.py
    - agentic_trader/worker/worker.py
    - tests/test_decision_engine.py
    - tests/test_feature_builder.py
    - tests/test_scanner_pipeline.py
key-decisions:
  - "BUY execution now requires bracket levels; the system no longer falls back to a plain market buy."
  - "Bracket levels are deterministic infrastructure derived from ATR or a bounded fallback percentage."
  - "Trade rows store only active bracket leg IDs and prices; lifecycle details live in BracketOrderEvent."
patterns-established:
  - "Agents decide direction/confidence; execution infrastructure computes protective order prices."
  - "Alpaca parent and child order IDs are persisted together with an append-only event."
requirements-completed: [EXEC-01]
completed: 2026-05-08
commit: 19f013a
---

# Phase 03 Plan 01 Summary: Bracket Entry Orders And Leg Tracking

**BUY decisions now submit protected Alpaca bracket orders and persist parent plus TP/SL leg state.**

## Accomplishments

- Added `AverageTrueRangeIndicator` and propagated `atr` into `MarketDataSnapshot`.
- Added `BracketPolicy` and `BracketLevels` for bounded ATR/fallback stop-loss and take-profit prices.
- Added Alpaca `buy_bracket()` support using `OrderClass.BRACKET`, `TakeProfitRequest`, and `StopLossRequest`.
- Updated `DecisionEngine` so BUY execution requires bracket levels and uses `buy_bracket()` instead of a plain `buy()`.
- Added `take_profit_order_id`, `stop_loss_order_id`, `take_profit_price`, and `stop_loss_price` to `Trade`.
- Added `BracketOrderEvent` and repository helpers for bracket submission auditing.
- Added idempotent Postgres schema alignment for the four new trade bracket columns.

## Verification

- `.venv/bin/python -m pytest tests/test_bracket_policy.py tests/test_alpaca_bracket_orders.py tests/test_decision_engine.py tests/test_feature_builder.py tests/test_worker_runtime_guards.py tests/test_scanner_pipeline.py` - 24 passed.
- `.venv/bin/python -m pytest` - 38 passed.
- `.venv/bin/ruff check .` - passed.
- `.venv/bin/ty check .` - passed.

## Notes

- `make test` was attempted, but this shell cannot find `uv` on PATH. The same pytest suite passed through the project `.venv`.
- Manual Alpaca Paper confirmation is still part of Phase 3 UAT: confirm a BUY creates a parent bracket plus TP/SL legs and local trade rows store all IDs.

---
*Phase: 03-agentic-execution-mix-sell*
*Completed: 2026-05-08*
