---
phase: 03-agentic-execution-mix-sell
plan: 02
subsystem: execution
tags: [position-review, bracket-replacement, alpaca, de-risking, worker]
requires:
  - phase: 03-agentic-execution-mix-sell
    provides: bracket order placement and leg tracking
provides:
  - scheduled open-position review job
  - de-risk-only exit decision validator
  - Alpaca replace-order integration
  - bracket leg replacement events
  - worker scheduler wiring for position review
affects: [phase-03-execution, phase-04-learning, worker, alpaca-controller, database]
key-files:
  created:
    - agentic_trader/worker/position_review.py
    - tests/test_position_review.py
  modified:
    - agentic_trader/controller/alpaca_controller.py
    - agentic_trader/database/repository.py
    - agentic_trader/worker/worker.py
    - tests/test_alpaca_bracket_orders.py
key-decisions:
  - "Position review reads current Alpaca positions before touching local bracket legs."
  - "Agentic exit review can only de-risk: tighten stops, lower take-profit targets, or close."
  - "Invalid or mismatched state records an event and makes no Alpaca replacement call."
patterns-established:
  - "Open-position management is separate from scanner/trade-job entry flow."
  - "Leg replacement updates the active order ID in the same unit of work as the lifecycle event."
requirements-completed: [EXEC-02, EXEC-03]
completed: 2026-05-08
commit: 19f013a
---

# Phase 03 Plan 02 Summary: Position Review And Bracket Leg Replacement

**Open long positions can now be reviewed on a schedule and adjusted only in conservative, de-risking directions.**

## Accomplishments

- Added `PositionReviewDecision`, `TechnicalExitReviewer`, and `validate_de_risk_only()`.
- Added `PositionReviewJob` that reads Alpaca positions once, queries open bracketed local trades, and handles mismatches safely.
- Added Alpaca `replace_order()` support for take-profit and stop-loss child legs.
- Added repository helpers to find bracketed open trades, record bracket lifecycle events, and update active leg IDs/prices.
- Wired `POSITION_REVIEW_INTERVAL`, `build_position_reviewer()`, and scheduled `position_review.run` into the worker.
- Added tests for de-risk validation, replacement calls, skipped invalid decisions, state mismatch events, and close behavior.

## Verification

- `.venv/bin/python -m pytest tests/test_position_review.py tests/test_alpaca_bracket_orders.py tests/test_decision_engine.py tests/test_worker_runtime_guards.py` - 24 passed.
- `.venv/bin/python -m pytest` - 38 passed.
- `.venv/bin/ruff check .` - passed.
- `.venv/bin/ty check .` - passed.

## Notes

- `make test` was attempted, but this shell cannot find `uv` on PATH. The project `.venv` checks passed.
- Manual Alpaca Paper UAT should confirm a replacement order returns a new child-leg ID and the local trade row updates to that new ID.

---
*Phase: 03-agentic-execution-mix-sell*
*Completed: 2026-05-08*
