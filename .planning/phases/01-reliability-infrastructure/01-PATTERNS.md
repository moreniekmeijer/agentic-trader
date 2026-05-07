# Phase 01: Reliability & Infrastructure - Patterns

## Architectural Patterns

### 1. Repository Pattern (Persistence)
- **Analogs**: `TradeRepository` and `WatchlistRepository` in `agentic_trader/database/repository.py`.
- **New Requirement**: Create a `SystemRepository` or extend `WatchlistRepository` to handle worker heartbeat and active symbol state.
- **Pattern**: The worker never touches SQLAlchemy models directly; it uses the Repository to persist state.

### 2. Mapper Pattern (Domain-to-ORM)
- **Analogs**: `agentic_trader/database/mapper.py`.
- **Pattern**: Pure functions that translate Pydantic models or domain objects into SQLAlchemy objects. This keeps the domain logic decoupled from the DB schema.

### 3. Job Orchestration (Scheduler)
- **Analogs**: `worker.py` using `APScheduler.BlockingScheduler`.
- **Pattern**: Periodic jobs are defined as top-level functions and added to the scheduler.
- **Modification**: Jobs like `pnl_sync` need to be modified for higher frequency and "catch-up" logic.

## Integration Points

### Alpaca Client Order ID
- **Location**: `agentic_trader/decision/engine.py` -> `DecisionEngine.execute_decision`.
- **Pattern**: Currently, `execute_decision` calls `controller.submit_order`. We need to pass the `decision_id` from our DB into the `client_order_id` field of the Alpaca request.

### Worker State Initialization
- **Location**: `agentic_trader/worker/worker.py` -> `if __name__ == "__main__":` block.
- **Pattern**: On startup, the worker currently initializes an empty `WorkerState()`.
- **New Pattern**: Initialization should involve `state.load_from_db()` to resume the previous watchlist.

## Schema Analog

### Heartbeat / System State
- **Analog**: `WatchlistEntry` has `added_at` and `is_active`.
- **Proposed Model**: `WorkerHeartbeat` table with `last_seen`, `worker_id` (for future scaling), and `current_watchlist` (JSONB symbols list).

```python
class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active_symbols: Mapped[list] = mapped_column(ARRAY(String(10)))
```
