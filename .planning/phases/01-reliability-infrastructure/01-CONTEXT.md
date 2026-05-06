# Phase 01: Reliability & Infrastructure - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensuring the "always-on" reliability of the trading system. This phase delivers a resilient worker capable of surviving interruptions (like closing a laptop) and resuming its exact state, while maintaining perfect synchronization with the Alpaca source of truth.

</domain>

<decisions>
## Implementation Decisions

### Worker Resilience & Deployment
- **D-01: Hybrid Persistence** — The worker's `WorkerState` (active watchlist and heartbeat) will be persisted in PostgreSQL.
- **D-02: RAM-to-SQL Split** — Large DataFrames (cached price history) will stay in memory. On restart, the worker re-fetches price history for the persisted watchlist symbols to ensure accuracy.
- **D-03: Resume-ability** — When the worker starts, it checks the DB for its last watchlist and checks Alpaca for any "missed" trade activities during its offline period.

### Idempotency & Safety
- **D-04: Decision-to-Client Mapping** — The database `decision.id` (UUID) will be mapped directly to the Alpaca `client_order_id`. 
- **D-05: Double-Order Prevention** — Alpaca's native idempotency (rejecting duplicate `client_order_id`) is used as the primary guard against duplicate trades during retries or crashes.

### Synchronization
- **D-06: Polling Cadence** — Shorten the `pnl_sync` and position reconciliation polling interval from 60 minutes to 1-5 minutes.
- **D-07: Catch-up friendly** — Polling logic must handle "catch-up" mode to process all activities that occurred since the last successful sync.

### the agent's Discretion
- Technical implementation of the serialization logic (how DataFrames are discarded/re-fetched).
- Specific heartbeat implementation in the DB.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Logic
- `agentic_trader/worker/worker.py` — Current scheduler and job management.
- `agentic_trader/worker/scan_state.py` — Current in-memory state management.
- `agentic_trader/decision/engine.py` — Current order execution and decision persistence.

### Integration
- `agentic_trader/controller/alpaca_controller.py` — Alpaca API wrapper.
- `agentic_trader/database/repository.py` — Persistence layer.

### Project Specs
- `.planning/REQUIREMENTS.md` — v1 requirements (RELI-01 to RELI-03).
- `.planning/research/STACK.md` — Research on Temporal/Celery vs. Polling reliability.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WorkerState`: Can be extended with `load_from_db()` and `save_to_db()` methods.
- `PnlSyncJob`: Can be modified to run at a higher frequency and handle catch-up logic.

### Established Patterns
- `BlockingScheduler`: Used for interval-based tasks; continues to be the primary driver.
- `RepositoryPattern`: Used for DB access; new methods needed for state persistence.

### Integration Points
- `DecisionEngine.execute_decision`: Where `client_order_id` must be injected.
- `worker.py`: Where the sync interval and state initialization happen.

</code_context>

<specifics>
## Specific Ideas
- "Always-on architecture" even when running locally on a laptop to ensure future cloud readiness.
- "Last Seen" heartbeat visible in the logs/DB for monitoring.

</specifics>

<deferred>
## Deferred Ideas
- **Temporal/Celery Migration**: Acknowledged as the "gold standard" for 24/7 reliability but deferred to v2 unless polling proves insufficient.
- **Webhooks/Streaming**: Deferred in favor of robust polling for better interruption-resilience on a laptop.

</deferred>

---

*Phase: 01-reliability-infrastructure*
*Context gathered: 2026-05-06*
