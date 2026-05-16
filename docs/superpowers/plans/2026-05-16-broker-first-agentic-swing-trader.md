# Broker-First Agentic Swing Trader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe, Alpaca-reconciled, multi-stock agentic swing trading app for 2-100 day stock holds and an initial 10,000 EUR budget.

**Architecture:** Use Alpaca as the operational source of truth. The local database stores audit history, decisions, snapshots, and learning data, but broker account, positions, orders, fills, and trade lifecycle are reconciled from Alpaca before every decision cycle. Agents produce recommendations; deterministic portfolio/risk/execution code decides whether an order is allowed and how large it may be.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, APScheduler/event worker, Alpaca Trading/Data APIs, existing market/fundamental/news providers, Pydantic models.

---

## Guiding Constraints

- Alpaca is the source of truth for account equity, cash, positions, open orders, fills, and order status.
- Trading style is stock-only, long-biased swing trading with expected holds between 2 and 100 days.
- The app manages multiple stocks as one portfolio, not isolated ticker decisions.
- Initial capital is 10,000 EUR, but execution sizing must use Alpaca account equity/cash in broker currency.
- Agents are advisory and comparative. Deterministic rules own capital allocation, risk limits, order sizing, and execution safety.
- Self-learning starts as structured observation and post-trade analysis, not automatic strategy mutation.

## Target Runtime Flow

1. Reconcile Alpaca account, positions, orders, fills, and recent activities.
2. Persist broker snapshot and mark any local lifecycle mismatches.
3. Refresh universe and candidate data on a swing-trading cadence.
4. Agents score technical, fundamental, sentiment, and portfolio context.
5. Portfolio manager compares all candidates and existing holdings together.
6. Risk allocator converts approved recommendations into target allocations and order intents.
7. Execution guard validates market hours, data freshness, duplicate orders, cash, exposure, and bracket protection.
8. Orders are submitted with idempotent `client_order_id` values.
9. Post-execution reconciliation updates local lifecycle from Alpaca.
10. Learning journal records decision context, outcome, and post-trade reflection.

---

## Phase 1: Broker Truth Layer

### Task 1: Add Broker Snapshot Models

**Files:**
- Create: `agentic_trader/broker/__init__.py`
- Create: `agentic_trader/broker/models.py`
- Modify: `agentic_trader/controller/alpaca_controller.py`

- [ ] Define Pydantic models for `BrokerAccount`, `BrokerPosition`, `BrokerOrder`, `BrokerFill`, `BrokerSnapshot`, and `BrokerSyncIssue`.
- [ ] Normalize Alpaca objects into simple internal models with strings/floats/datetimes only.
- [ ] Include broker-native IDs: `order_id`, `client_order_id`, `asset_id`, `symbol`, `status`, `side`, `qty`, `filled_qty`, `filled_avg_price`.
- [ ] Add controller methods for account, positions, open orders, recent closed orders, and fill activities.
- [ ] Keep methods side-effect free; fetching a snapshot must not mutate the DB.

### Task 2: Build Broker Snapshot Service

**Files:**
- Create: `agentic_trader/broker/snapshot.py`
- Modify: `agentic_trader/worker/worker.py`

- [ ] Implement `BrokerSnapshotService.fetch_snapshot()`.
- [ ] Resolve Alpaca symbols consistently, including `BRK-B` versus `BRK.B`.
- [ ] Compute derived broker state: total equity, cash, buying power, invested value, open risk estimate, open order symbols.
- [ ] Log snapshot summary at the start of every worker cycle.
- [ ] Ensure all trading jobs receive the latest broker snapshot instead of querying Alpaca independently.

### Task 3: Persist Broker Audit State

**Files:**
- Modify: `agentic_trader/database/models.py`
- Modify: `agentic_trader/database/repository.py`
- Modify: `agentic_trader/database/session.py`
- Modify: `agentic_trader/api/schemas.py`
- Modify: `agentic_trader/api/app.py`

- [ ] Add `BrokerSnapshotRecord` for account-level snapshots.
- [ ] Add `OrderIntent` for local intended actions before broker submission.
- [ ] Add `OrderLifecycle` for broker order status over time.
- [ ] Add `PositionLifecycle` for holding state, thesis, invalidation, and expected horizon.
- [ ] Expose `/broker/snapshot`, `/orders`, and `/positions` API views using broker-reconciled records.
- [ ] Replace ad hoc `create_all` schema patching with an explicit migration approach before live trading.

---

## Phase 2: Portfolio Rules For 10,000 EUR

### Task 4: Add Portfolio Policy

**Files:**
- Create: `agentic_trader/portfolio/__init__.py`
- Create: `agentic_trader/portfolio/policy.py`
- Modify: `.env.example`

- [ ] Add config defaults: `TARGET_BUDGET_EUR=10000`, `MAX_OPEN_POSITIONS=8`, `MIN_CASH_RESERVE_PCT=0.15`, `MAX_POSITION_PCT=0.18`, `MAX_TRADE_RISK_PCT=0.01`, `MAX_SECTOR_PCT=0.35`, `MIN_HOLD_DAYS=2`, `MAX_HOLD_DAYS=100`.
- [ ] Use Alpaca equity and cash for execution limits. Treat the EUR budget as an operator-level target and reporting anchor.
- [ ] Block new buys when cash reserve would be violated.
- [ ] Block new buys when open position count or sector exposure cap would be violated.
- [ ] Block any single trade whose stop-loss risk exceeds the configured portfolio risk.

### Task 5: Add Deterministic Allocator

**Files:**
- Create: `agentic_trader/portfolio/allocator.py`
- Modify: `agentic_trader/risk/engine.py`

- [ ] Convert ranked buy candidates and existing holdings into target weights.
- [ ] Prioritize sells/reductions before buys.
- [ ] Size buys from available cash after reserve, max position size, and stop-loss risk.
- [ ] Support partial allocation when several high-quality candidates compete for limited cash.
- [ ] Return `OrderIntent` objects, not broker orders.

---

## Phase 3: Safe Agentic Decision Layer

### Task 6: Rebuild Candidate Pipeline

**Files:**
- Modify: `agentic_trader/scanner/models.py`
- Modify: `agentic_trader/scanner/engine.py`
- Modify: `agentic_trader/worker/worker.py`

- [ ] Use staged candidates: quality universe, technical shortlist, sentiment-enriched shortlist, portfolio-ranked shortlist.
- [ ] Refresh fundamentals weekly, technicals daily, sentiment daily or before the decision cycle.
- [ ] Keep market snapshots and agent responses attached to each candidate.
- [ ] Avoid using overbought short-term spikes as buy signals for a 2-100 day strategy unless fundamentals and trend agree.

### Task 7: Constrain Agent Roles

**Files:**
- Modify: `agentic_trader/agents/synthesizer/agent.py`
- Modify: `agentic_trader/agents/portfolio/agent.py`
- Create: `agentic_trader/decision/portfolio_manager.py`

- [ ] Make agents produce structured recommendations: `BUY`, `HOLD`, `REDUCE`, `EXIT`, with confidence, thesis, invalidation, horizon, and evidence.
- [ ] Keep the LLM comparative: it may rank candidates and explain tradeoffs, but it may not choose raw quantity or submit orders.
- [ ] Require every buy recommendation to include a clear thesis, invalidation condition, and expected holding horizon.
- [ ] Treat sentiment as a soft modifier, not a hard buy trigger.
- [ ] Block LLM recommendations that contradict broker/risk facts.

### Task 8: Add Deterministic Bracket Policy

**Files:**
- Create: `agentic_trader/decision/bracket_policy.py`
- Modify: `agentic_trader/decision/engine.py`
- Modify: `agentic_trader/services/market_data/indicators/atr.py`

- [ ] Derive stop-loss and take-profit from ATR and swing horizon.
- [ ] Enforce positive prices, Alpaca-compatible rounding, minimum risk distance, and maximum loss per trade.
- [ ] Prefer bracket/OCO orders for new long positions.
- [ ] Store bracket parent and child leg IDs after order submission.
- [ ] Do not accept LLM-generated stop-loss or take-profit prices unless they pass deterministic validation.

---

## Phase 4: Execution And Reconciliation

### Task 9: Add Order Intent Execution

**Files:**
- Modify: `agentic_trader/controller/alpaca_controller.py`
- Modify: `agentic_trader/decision/engine.py`
- Create: `agentic_trader/execution/__init__.py`
- Create: `agentic_trader/execution/executor.py`

- [ ] Submit only validated `OrderIntent` objects.
- [ ] Use stable `client_order_id` values derived from local intent ID, symbol, side, and cycle timestamp.
- [ ] Block duplicate orders when Alpaca has open orders for the same symbol.
- [ ] Block execution when broker snapshot is stale.
- [ ] Start with manual approval mode: write intents and require an operator flag before broker submission.

### Task 10: Replace PnL Sync With Fill-Based Lifecycle

**Files:**
- Create or replace: `agentic_trader/worker/pnl_sync.py`
- Modify: `agentic_trader/database/repository.py`
- Modify: `agentic_trader/services/reflection/reflector_service.py`

- [ ] Stop expecting Alpaca activities to provide local `realized_pl`.
- [ ] Use Alpaca fills as the source of executed buy/sell prices and quantities.
- [ ] Compute local realized PnL from broker-confirmed fills and matched lots.
- [ ] Keep unresolved mismatches as `needs_reconciliation` instead of forcing `pnl = 0`.
- [ ] Trigger reflection only when a lifecycle has a confirmed closed position and realized result.

### Task 11: Add Position Review

**Files:**
- Create: `agentic_trader/worker/position_review.py`
- Modify: `agentic_trader/worker/worker.py`

- [ ] Review open holdings daily against thesis, invalidation, technical deterioration, and max holding horizon.
- [ ] Allow only de-risking actions from review: `HOLD`, `TIGHTEN_STOP`, `REDUCE`, `EXIT`.
- [ ] Never let a review increase position size.
- [ ] Record every accepted and rejected review action for learning.

---

## Phase 5: Learning Foundation

### Task 12: Add Structured Learning Journal

**Files:**
- Create: `agentic_trader/learning/__init__.py`
- Create: `agentic_trader/learning/models.py`
- Create: `agentic_trader/learning/journal.py`
- Modify: `agentic_trader/database/models.py`
- Modify: `agentic_trader/database/repository.py`

- [ ] Store each decision with candidate features, agent votes, portfolio state, broker state, thesis, invalidation, horizon, and final action.
- [ ] Store rejected recommendations and the deterministic rule that blocked them.
- [ ] Store post-trade outcomes: realized PnL, holding days, max favorable excursion, max adverse excursion, exit reason, and rule/agent attribution.
- [ ] Make learning data queryable by symbol, sector, setup type, agent, and horizon.

### Task 13: Add Reflection Without Self-Mutation

**Files:**
- Modify: `agentic_trader/agents/reflector/agent.py`
- Modify: `agentic_trader/services/reflection/reflector_service.py`
- Create: `agentic_trader/learning/scorecard.py`

- [ ] Generate post-trade lessons only from confirmed closed lifecycles.
- [ ] Save lessons as observations, not code changes or hidden memory.
- [ ] Compute agent scorecards from measurable outcomes.
- [ ] Feed summarized lessons into future agent prompts as context.
- [ ] Require operator approval before changing strategy weights, risk caps, or screening rules.

---

## Phase 6: Operational Dashboard

### Task 14: Expose Portfolio Control Surfaces

**Files:**
- Modify: `agentic_trader/api/app.py`
- Modify: `agentic_trader/api/schemas.py`

- [ ] Add endpoints for broker snapshot, current positions, open orders, order intents, decisions, rejected recommendations, lifecycle mismatches, and learning scorecards.
- [ ] Add a kill-switch endpoint that disables broker submissions but keeps scans and analysis running.
- [ ] Add manual approval endpoint for pending order intents.
- [ ] Add paper/live mode visibility in every execution-facing response.

---

## Suggested Execution Order

1. Phase 1: broker truth layer.
2. Phase 2: portfolio policy and allocator.
3. Phase 4 Task 9: manual approval order-intent execution.
4. Phase 3: agentic decision layer.
5. Phase 4 Tasks 10-11: fill lifecycle and position review.
6. Phase 5: learning foundation.
7. Phase 6: dashboard and operator controls.

## Definition Of Ready For Paper Auto-Trading

- Every cycle begins with a fresh Alpaca snapshot.
- Local positions and orders reconcile with Alpaca or produce explicit mismatch records.
- New orders are created only as validated order intents.
- Manual approval mode works end to end.
- Bracket protection is mandatory for new long positions.
- Portfolio rules block over-allocation beyond the 10,000 EUR operating budget.
- Every executed trade has a stored thesis, invalidation, horizon, and broker order lifecycle.
- Reflection uses confirmed closed trades only.
