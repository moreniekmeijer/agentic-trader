# Roadmap: Agentic Trader

## Overview

The journey from a basic trading script to a fully automated, self-learning agentic system. We start by stabilizing the core execution engine, then expand into sophisticated scanning and decision logic, and finally close the loop with an attribution-based learning system.

## Phases

- [ ] **Phase 1: Reliability & Infrastructure** — Stabilize worker execution and trade synchronization.
- [ ] **Phase 2: Multi-Stage Scanner** — Implement the agentic scanning funnel (Fundamentals/Technicals/Sentiment).
- [ ] **Phase 3: Agentic Execution (Mix Sell)** — Coordinate Alpaca bracket orders with agentic profit targets.
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
- [ ] 01-01: Stabilize worker execution loop and recovery logic.
- [ ] 01-02: Implement robust Alpaca fill/position synchronization.

### Phase 2: Multi-Stage Scanner
**Goal**: Replace the hardcoded scanner with a dynamic, agent-driven funnel.
**Depends on**: Phase 1
**Requirements**: SCAN-01, SCAN-02, SCAN-03, SCAN-04
**Success Criteria**:
  1. System generates a weekly "Quality Universe" based on fundamentals.
  2. System generates a daily "Active Shortlist" based on technical timing.
  3. Sentiment agent re-evaluates shortlist candidates before discussion.
**Plans**: 2 plans

Plans:
- [ ] 02-01: Implement Fundamental and Technical scanner agents.
- [ ] 02-02: Integrate News/Sentiment agent into the scanning funnel.

### Phase 3: Agentic Execution (Mix Sell)
**Goal**: Combine automated bracket orders with subjective agentic profit taking.
**Depends on**: Phase 2
**Requirements**: EXEC-01, EXEC-02, EXEC-03
**Success Criteria**:
  1. Every entry order is accompanied by a Stop Loss and Take Profit leg in Alpaca.
  2. System re-evaluates open positions and successfully modifies bracket legs (e.g., trailing stops or lower profit targets).
**Plans**: 2 plans

Plans:
- [ ] 03-01: Implement bracket order placement and leg tracking.
- [ ] 03-02: Implement agentic re-evaluation and leg modification logic.

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
| 1. Reliability | 0/2 | Not started | - |
| 2. Scanner | 0/2 | Not started | - |
| 3. Execution | 0/2 | Not started | - |
| 4. Learning | 0/2 | Not started | - |

---
*Roadmap defined: 2026-05-05*
*Last updated: 2026-05-05 after requirements definition*
