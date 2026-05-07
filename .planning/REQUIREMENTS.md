# Requirements: Agentic Trader

**Defined:** 2026-05-05
**Core Value:** A fully automated agentic trading system that learns from historical outcomes through attribution and signal snapshotting, while leveraging Alpaca for mechanical risk management.

## v1 Requirements

### Core Execution & Reliability (RELI)

- [ ] **RELI-01**: Worker process can run continuously during trading hours without manual intervention.
- [ ] **RELI-02**: All trade execution tasks use unique decision IDs as idempotency keys to prevent duplicate Alpaca orders.
- [ ] **RELI-03**: Database `trades` table is automatically synchronized with Alpaca FILL activities and position states.

### Advanced Multi-Stage Scanner (SCAN)

- [x] **SCAN-01**: Implement a multi-stage funnel: Fundamentals Filter → Technical Setup → Sentiment/Event Check.
- [x] **SCAN-02**: Specialized agent for weekly fundamental quality screening (Quality Universe).
- [x] **SCAN-03**: Specialized agent for daily technical timing on the Quality Universe (Active Shortlist).
- [x] **SCAN-04**: Specialized agent for real-time news/sentiment analysis on shortlist candidates.

### Execution & Mix Sell Logic (EXEC)

- [ ] **EXEC-01**: Entry orders are placed as Alpaca "bracket" orders with initial Stop Loss and Take Profit legs.
- [ ] **EXEC-02**: System periodically re-evaluates open positions via agents to identify early exit profit targets.
- [ ] **EXEC-03**: System can modify existing Alpaca bracket legs (Take Profit/Stop Loss) using the `replace_order` API.

### Self-Learning & Attribution (LRN)

- [ ] **LRN-01**: Capture and store the full vector of agent signals and indicator values at the moment of decision (Signal Snapshotting).
- [ ] **LRN-02**: Attribution agent correlates signal snapshots with realized P&L outcomes for closed trades.
- [ ] **LRN-03**: Discussion agent weights (Technical vs. Fundamental) are adjusted based on historical attribution performance.

## v2 Requirements

### Analytics & UI

- **ANLY-01**: Frontend dashboard to visualize decision history, trade outcomes, and agent performance.
- **ANLY-02**: Manual feedback/labeling system to guide agent learning from user-defined "good" or "bad" trades.

### Risk Management

- **RISK-01**: Advanced portfolio-level risk management (e.g., sector exposure limits, correlated asset caps).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Intraday Trading | High data/latency complexity; Yahoo Finance is insufficient for sub-hour trading. |
| Live Trading | Restricted to Paper Trading mode for v1 safety. |
| Message Broker | Celery/Temporal deferred to v2 unless reliability requires it earlier. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RELI-01 | Phase 1 | Pending |
| RELI-02 | Phase 1 | Pending |
| RELI-03 | Phase 1 | Pending |
| SCAN-01 | Phase 2 | Complete |
| SCAN-02 | Phase 2 | Complete |
| SCAN-03 | Phase 2 | Complete |
| SCAN-04 | Phase 2 | Complete |
| EXEC-01 | Phase 3 | Pending |
| EXEC-02 | Phase 3 | Pending |
| EXEC-03 | Phase 3 | Pending |
| LRN-01 | Phase 4 | Pending |
| LRN-02 | Phase 4 | Pending |
| LRN-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-05*
*Last updated: 2026-05-07 after Phase 2 security verification*
