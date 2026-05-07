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

The scanner should be a staged discovery pipeline, not a monolithic "Scanner Agent" that owns every concern.

### Boundary Model
1.  **Providers** fetch external data.
    *   Example: `YahooFinanceProvider`.
    *   Providers live behind service abstractions so `yfinance` can be replaced or supplemented later if rate limits or data quality become a problem.
2.  **Services / engines** compute facts and reusable analysis.
    *   Example: market data snapshots, fundamentals snapshots, technical indicators.
    *   These should be deterministic and cache-friendly.
3.  **Evaluators / agents** turn facts into judgment-shaped outputs.
    *   Example: technical, fundamentals, or sentiment judgment with confidence and reasons.
    *   These can still return `AgentResponse`-style outputs, but they should not be the only carrier of important market timing data.
4.  **Scanner stages** rank and filter candidates.
    *   Weekly fundamentals stage builds the Quality Universe.
    *   Daily technical stage builds the long-only Active Shortlist.
    *   Sentiment stage enriches candidates as soft input.
5.  **Trade job** consumes enriched candidates and stays mostly deterministic.
    *   It should apply final synthesis, risk checks, order submission, and persistence.
    *   It should not re-fetch or reconstruct the full analysis context from scratch.

### Candidate Context

Scanner outputs should be enriched candidate objects, not only symbols or compressed votes.

Each candidate should preserve enough context for execution and future learning:
*   symbol
*   stage membership (`Quality Universe`, `Active Shortlist`)
*   market snapshots and technical timing state
*   fundamentals snapshot and quality score
*   sentiment score/confidence and reasons when available
*   evaluator votes / `AgentResponse`-style judgments
*   freshness timestamps and stage scores

This keeps "timing the market" information available to the trade flow and makes future attribution/self-learning feasible.

### Data Flow
*   **Worker** → staged scanner pipeline (Universe: S&P 500)
*   **Provider/service layer** → facts, indicators, fundamentals, sentiment inputs
*   **Evaluator/agent layer** → confidence, reasons, and judgment outputs
*   **Scanner pipeline** → enriched `CandidateContext` shortlist
*   **Decision synthesis + trade job** → deterministic risk checks and execution

This decouples facts from judgments and keeps provider concerns, agentic reasoning, and trade execution from bleeding into each other.

## Trade Tracking (Source of Truth)

*   **Logic**: Alpaca is the source of truth.
*   **Sync**: The `PnlSyncJob` should be enhanced to poll for `order_status` changes, not just `FILL` activities.
*   **Consistency**: Ensure the `trades` table in PostgreSQL stays in sync with Alpaca positions using a periodic "Position Reconciliation" job.
