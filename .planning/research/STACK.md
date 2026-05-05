# Research: Technology Stack (2025)

## Worker Reliability & Orchestration

For an automated trading system, reliability is paramount. The current `APScheduler` setup is sufficient for prototyping but has significant limitations for 24/7 mission-critical operations.

### Recommendations:
1.  **Temporal (Durable Execution)**:
    *   **Rationale**: Gold standard for high-reliability financial workflows. Automatically persists state, handles retries, and resumes exactly where it left off after a crash.
    *   **Use Case**: Core trade execution (risk check → order → fill sync → DB update).
2.  **Celery + RabbitMQ**:
    *   **Rationale**: Robust distributed task queue. Better for parallelizing compute-intensive tasks like scanning hundreds of symbols or running backtests.
3.  **Idempotency**:
    *   **Critical**: Every task must be idempotent. Use unique IDs (e.g., decision IDs) when interacting with Alpaca to prevent duplicate orders.

## Data Providers

| Provider | Purpose | Note |
| :--- | :--- | :--- |
| **Yahoo Finance** | Fundamentals & Historical | Free but occasionally flaky. Best for swing trading (daily/4h). |
| **Alpaca API** | Live/Paper Execution | Native integration. Provides real-time data if account is funded ($100 min). |
| **Sentiment APIs** | News & Social | Consider **Alternative Data** providers like Alpha Vantage or specialized LLM-based news aggregators. |

## Persistence

*   **PostgreSQL (Current)**:
    *   **Scalability**: Use **TimescaleDB** extension if transaction volume grows significantly (handles time-series data with automatic partitioning).
    *   **State Snapshotting**: Use JSONB columns to store the full "signal state" at decision time for flexible retrospective analysis.

## Summary Checklist
- [ ] Implement unique idempotency keys for all Alpaca orders.
- [ ] Use JSONB for storing flexible agent confidence/indicator snapshots.
- [ ] Consider migrating the `trade_job` to a more durable execution framework (like Temporal) if reliability becomes an issue.
