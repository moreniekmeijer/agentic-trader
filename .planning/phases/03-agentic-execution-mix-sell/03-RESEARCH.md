# Phase 03: Agentic Execution (Mix Sell) - Research

**Researched:** 2026-05-08
**Status:** Complete

## Research Question

What do we need to know to plan Phase 03 well: protected Alpaca bracket entries, local leg tracking, and conservative agentic exit adjustments?

## Sources

- Alpaca Trading API orders overview: https://docs.alpaca.markets/docs/orders-at-alpaca
- Alpaca `alpaca-py` order examples: https://docs.alpaca.markets/docs/working-with-orders
- Alpaca Replace Order by ID reference: https://docs.alpaca.markets/reference/patchorderbyorderid-1
- Local SDK lockfile: `uv.lock` pins `alpaca-py==0.43.2`
- Local SDK introspection with `.venv/bin/python`

## Key Findings

### Bracket Orders

Alpaca bracket orders are the correct primitive for Phase 03. A bracket order submits an entry order and, after the entry fills, activates two conditional exit orders:
- take-profit leg: limit order
- stop-loss leg: stop or stop-limit order

For a buy bracket order:
- `take_profit.limit_price` must be above `stop_loss.stop_price`.
- both take-profit limit and stop-loss stop prices are required.
- `time_in_force` must be `day` or `gtc`.
- extended hours are not supported for bracket orders.
- the child orders can be retrieved as nested `legs` when order queries use `nested=True`.
- order replacement can update `limit_price` and `stop_price` for the relevant open leg.

### Installed SDK Surface

The installed `alpaca-py` version exposes the request classes and methods needed for this phase:

```text
MarketOrderRequest
TakeProfitRequest(limit_price: float)
StopLossRequest(stop_price: float, limit_price: float | None)
ReplaceOrderRequest(qty, time_in_force, limit_price, stop_price, trail, client_order_id)
GetOrdersRequest(status, limit, nested, side, symbols)
GetOrderByIdRequest(nested: bool)
OrderClass.BRACKET
TradingClient.submit_order(order_data)
TradingClient.replace_order_by_id(order_id, order_data)
TradingClient.get_orders(filter=GetOrdersRequest(...))
TradingClient.get_order_by_id(order_id, filter=GetOrderByIdRequest(...))
```

This means the implementation should stay inside `alpaca-py`; no raw REST call is needed for bracket placement or replacement.

### Replacement Semantics

Alpaca replacement has race conditions that matter for safety:
- a successful replace response does not guarantee the original order was replaced if the old order fills before the replacement reaches the venue.
- some states cannot be replaced, including `accepted`, `pending_new`, `pending_cancel`, and `pending_replace`.
- replacing returns a new Order object with a new order ID.

Planning implication: bracket leg replacement must be treated as an order lifecycle event, not an in-place mutation. The local active leg ID must be updated from the replacement response, and the old/new IDs should be recorded in the event log.

### Long-Only Guard

Alpaca supports opening shorts by submitting a sell order without an existing long position. Phase 03 explicitly forbids this. The system must keep the existing `get_available_qty()` guard and make `SELL` close/reduce only. For bracket entries, only `BUY` should use bracket order submission in v1.

### Price Policy

Market orders can slip. Phase 03 still uses market-style entries, but bracket levels need deterministic reference prices before submission. The safest planning shape:
- derive initial bracket levels from the latest cached daily market reference in `CandidateContext`.
- use daily volatility/ATR-style risk distance when available.
- fallback to fixed percentages if ATR cannot be computed.
- round submitted limit/stop prices to Alpaca-compatible decimal increments.

The current market-data pipeline already has daily OHLCV bars from yfinance. It does not yet expose ATR. Planning should add a small ATR indicator and extend `MarketDataSnapshot` so bracket policy can consume `daily.price` and `daily.atr`.

### Persistence

Current `Trade` has only `alpaca_order_id`, which can represent the parent entry order. Phase 03 needs only a few active operational fields:
- active take-profit order ID
- active stop-loss order ID
- last submitted take-profit price
- last submitted stop-loss price

An append-only `BracketOrderEvent` table is useful, but it should only record actual order lifecycle changes:
- bracket submitted
- leg IDs discovered/refreshed
- leg replaced
- early close requested/submitted
- repair skipped because Alpaca/local state disagreed

Avoid mirroring every Alpaca order field locally. Alpaca remains source of truth.

### Schema Risk

The project currently uses `Base.metadata.create_all()`, which creates missing tables but does not add columns to existing tables. Phase 03 adds `Trade` columns and a new event table, so the plan must include a schema-alignment task. Since Alembic is not set up yet, the minimum viable approach for this phase is:
- keep ORM models aligned with mapper/repository/API usage.
- add tests against the model/mappers.
- include a clear dev database migration path before worker runtime verification.

Planner note: do not silently add model fields without also planning how the existing Docker Postgres database gets those fields.

## Recommended Plan Split

### Plan 03-01: Bracket Placement And Leg Tracking

Goal: make accepted BUY decisions submit protected bracket entries and persist active bracket identifiers.

Recommended work:
- Add ATR/volatility fields to market snapshots.
- Add deterministic bracket policy.
- Add Alpaca bracket submission and nested order retrieval helpers.
- Add minimal trade columns and bracket event model.
- Update `DecisionEngine` to call bracket buy for BUY decisions.
- Preserve SELL as close/reduce-only.
- Add tests for bracket policy, Alpaca request construction, leg extraction, and persistence mapping.

### Plan 03-02: Position Review And Leg Replacement

Goal: periodically review open positions and conservatively adjust/close positions using Alpaca replace/cancel/order APIs.

Recommended work:
- Add an exit review model/service that can produce `HOLD`, `TIGHTEN_STOP`, `LOWER_TAKE_PROFIT`, or `CLOSE`.
- Add Alpaca replace helper around `replace_order_by_id`.
- Add safety validation so stop changes only tighten and target changes only lower risk for long positions.
- Add a scheduled `position_review_job`.
- Add event logging for every actual replacement or skipped repair.
- Add tests for de-risk-only enforcement and replacement ID updates.

## Validation Architecture

Automated tests should cover:
- bracket level calculation from ATR and fixed fallback.
- Alpaca bracket request construction with `OrderClass.BRACKET`, `TakeProfitRequest`, and `StopLossRequest`.
- extraction and persistence of take-profit and stop-loss leg IDs from nested order responses.
- long-only SELL behavior: no owned quantity means no order submission.
- replace-order helper updates active IDs from replacement response.
- exit review never loosens stop loss or increases risk.
- worker scheduling includes `position_review_job`.

Manual verification should cover:
- paper bracket order submission creates parent plus take-profit/stop-loss legs in Alpaca.
- local DB stores parent, current TP leg, current SL leg, and event record.
- replacing one leg in paper updates local active ID and records an event.
- worker startup with existing DB schema does not crash after schema changes are applied.

## Open Risks

- The current project has no formal migration tool. This phase can proceed with a minimal dev-safe schema path, but Alembic remains a larger hardening item.
- `replace_order_by_id` can race with fills. The implementation must verify Alpaca state after replacement and avoid assuming success means the old leg disappeared.
- yfinance market data may be stale or unavailable. Bracket policy must fail closed when no trusted price exists.

## Research Complete

This research is sufficient to plan Phase 03.

