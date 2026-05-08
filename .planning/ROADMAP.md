# Roadmap: Agentic Trader

## Overview

The journey from a basic trading script to a fully automated, self-learning agentic system. We start by stabilizing the core execution engine, then expand into sophisticated scanning and decision logic, and finally close the loop with an attribution-based learning system.

## Phases

- [x] **Phase 1: Reliability & Infrastructure** — Stabilize worker execution and trade synchronization.
- [x] **Phase 2: Multi-Stage Scanner** — Implement the agentic scanning funnel (Fundamentals/Technicals/Sentiment).
- [ ] **Phase 3: Agentic Execution (Mix Sell)** — Coordinate Alpaca bracket orders with agentic profit targets. *(Implemented; pending UAT)*
- [ ] **Phase 4: Attribution & Learning** — Close the loop with signal snapshotting and Bayesian weight updates.

## Phase Details

### Phase 1: Reliability & Infrastructure
**Goal**: Ensure the system can run 24/7 with perfect trade synchronization between Alpaca and the local database.
**Depends on**: Initial codebase
**Requirements**: RELI-01, RELI-02, RELI-03
**Success Criteria**:
  1. Worker runs continuously during trading hours with automated recovery.
  2. Every trade placed has a unique idempotency key (decision_id) in Alpaca.
  3. Database `trades` table accurately reflects Alpaca FILLs and position states within 1 minute of activity.
**Plans**: 2 plans

Plans:
- [x] 01-01: Stabilize worker execution loop and recovery logic.
- [x] 01-02: Implement robust Alpaca fill/position synchronization.

### Phase 2: Multi-Stage Scanner
**Goal**: Replace the hardcoded scanner with a staged discovery funnel that preserves rich candidate context for deterministic trade execution.
**Depends on**: Phase 1
**Requirements**: SCAN-01, SCAN-02, SCAN-03, SCAN-04
**Architecture Notes**:
  1. Providers/services fetch and compute facts; they remain swappable so `yfinance` can be replaced or supplemented later.
  2. Evaluators/agents turn facts into judgment-shaped outputs with confidence and reasons.
  3. Scanner stages produce enriched `CandidateContext` outputs, not just symbols or compressed votes.
  4. The trade job consumes enriched candidates and stays mostly deterministic: risk checks, final synthesis, order execution, and persistence.
**Success Criteria**:
  1. System generates a weekly "Quality Universe" based on fundamentals.
  2. System generates a daily "Active Shortlist" based on technical timing.
  3. Sentiment agent re-evaluates shortlist candidates before discussion.
  4. Scanner outputs preserve timing, fundamentals, sentiment, scores, reasons, and freshness context for later attribution.
**Plans**: 2 plans

Plans:
- [x] 02-01: Implement Quality Universe, long-only shortlist, and `CandidateContext`.
- [x] 02-02: Integrate sentiment soft input and scanner-oriented worker flow.

### Phase 3: Agentic Execution (Mix Sell)
**Goal**: Combine automated bracket orders with subjective agentic profit taking.
**Depends on**: Phase 2
**Requirements**: EXEC-01, EXEC-02, EXEC-03
**Success Criteria**:
  1. Every entry order is accompanied by a Stop Loss and Take Profit leg in Alpaca.
  2. System re-evaluates open positions and successfully modifies bracket legs (e.g., trailing stops or lower profit targets).
**Plans**: 2 plans

Plans:
- [x] 03-01: Implement bracket order placement and leg tracking. *(Wave 1)*
- [x] 03-02: Implement agentic re-evaluation and leg modification logic. *(Wave 2; depends on 03-01)*

**Cross-cutting constraints:**
  1. Execution stays long-only; `SELL` closes/reduces existing long positions only.
  2. Every accepted `BUY` entry must use an Alpaca bracket order with stop-loss and take-profit legs.
  3. Agentic exit review may only de-risk: tighten stops, lower targets, or close/reduce.
  4. Alpaca remains source of truth for active order and position state.

### Phase 4: Attribution & Learning
**Goal**: Implement the self-learning loop by correlating signal states with P&L.
**Depends on**: Phase 3
**Requirements**: LRN-01, LRN-02, LRN-03
**Success Criteria**:
  1. Every decision record contains a full JSONB snapshot of all signals and confidence levels.
  2. Attribution agent produces a report correlating specific signal patterns with profit outcomes.
  3. Discussion weights are automatically updated based on attribution findings.
**Plans**: 2 plans

Plans:
- [ ] 04-01: Implement signal state snapshotting at decision time.
- [ ] 04-02: Implement the Attribution Agent and Bayesian weight updating.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Reliability | 2/2 | Complete | 2026-05-07 |
| 2. Scanner | 2/2 | Complete | 2026-05-07 |
| 3. Execution | 2/2 | Ready for UAT | - |
| 4. Learning | 0/2 | Not started | - |

---
*Roadmap defined: 2026-05-05*
*Last updated: 2026-05-08 after Phase 3 execution*
