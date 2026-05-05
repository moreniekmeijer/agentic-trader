# Research: System Architecture

## Alpaca Bracket Coordination

Implementing "Mix" sell logic requires coordinating Alpaca's automated risk management (stops) with agentic exit logic (profit targets).

### Implementation Pattern:
1.  **Placement**:
    *   Place a `bracket` order via Alpaca with a standard Stop Loss and Take Profit.
    *   This provides a "hard floor" (stop loss) and "default ceiling" (take profit).
2.  **Coordination**:
    *   When an agent re-evaluates an open position and decides to exit early (profit target reached or thesis invalidated), the system must **modify** the existing bracket legs.
    *   **Crucial**: Use `replace_order` on the specific leg ID (retrieved from the parent order's `legs` attribute).
    *   **Leg 0**: Typically the Take Profit leg.
    *   **Leg 1**: Typically the Stop Loss leg.
3.  **Idempotency**:
    *   Store the Alpaca `order_id` for each leg in the `trades` table to allow quick lookup and modification.

## Agentic Scanner Layer

Instead of a monolithic `ScannerEngine`, use a "Scanner Agent" that manages the funnel.

### Data Flow:
*   **Worker** → **Scanner Agent** (Universe: S&P 500)
*   **Scanner Agent** → calls **Fundamentals Engine** (Filter for Quality)
*   **Scanner Agent** → calls **Market Data Engine** (Filter for Setup)
*   **Scanner Agent** → returns **Shortlist** to the worker.

This decouples the "How to scan" (logic) from the "What to scan" (engine).

## Trade Tracking (Source of Truth)

*   **Logic**: Alpaca is the source of truth.
*   **Sync**: The `PnlSyncJob` should be enhanced to poll for `order_status` changes, not just `FILL` activities.
*   **Consistency**: Ensure the `trades` table in PostgreSQL stays in sync with Alpaca positions using a periodic "Position Reconciliation" job.
