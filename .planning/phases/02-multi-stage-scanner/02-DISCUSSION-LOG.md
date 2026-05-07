# Phase 02: Multi-Stage Scanner - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 02-multi-stage-scanner
**Areas discussed:** Fundamentals funnel size, technical shortlist direction, sentiment role, source universe, worker evolution, service/agent boundaries, provider swappability, token/API budget, future learning

---

## Fundamentals Stage

| Option | Description | Selected |
|--------|-------------|----------|
| Top 10 | Very tight universe, highest conviction only | |
| Top 30 | Balanced intermediate universe for now | ✓ |
| Threshold-based | Include all names above a score cutoff | |

**User's choice:** Top 30.

---

## Technical Stage

| Option | Description | Selected |
|--------|-------------|----------|
| Long-only shortlist | Technical stage only surfaces new long entry candidates | ✓ |
| Bidirectional scan | Technical stage can surface both bullish and bearish candidates | |

**User's choice:** Long-only shortlist.

---

## Sentiment Stage

| Option | Description | Selected |
|--------|-------------|----------|
| Hard gate | Remove names from the shortlist when sentiment fails | |
| Soft input | Return score/confidence and reasons for downstream discussion | ✓ |

**User's choice:** Soft input.
**Notes:** User described the desired shape as similar to an `AgentResponse`: score/confidence plus reasons.

---

## Universe Source

| Option | Description | Selected |
|--------|-------------|----------|
| S&P 500 only | Keep scanner source universe tightly bounded | ✓ |
| Expanded universe | Broader equities universe | |

**User's choice:** S&P 500 only.

---

## Worker Evolution

**Question raised by user:** whether the "agentic" layer should already begin during the scan stage, and what the future role of `worker.py` is.

**Outcome:** Yes — Phase 2 should make the scanner itself more agentic through staged passes. `worker.py` should evolve into an orchestrator of separate scanner stages and cadences, while trade discussion/execution remains downstream.

---

## Architecture Boundary Follow-Up

**Question raised by user:** whether technical/fundamental components should be multi-purpose, whether they should be called agents, and how to prevent `trade_job` from missing timing context.

**Outcome:** Phase 2 should separate facts, judgments, scanner stages, and deterministic execution:
- providers/services fetch and compute facts
- evaluators/agents produce confidence/reasoning outputs
- scanner stages produce enriched candidate context
- final synthesis combines judgments
- trade execution remains mostly deterministic

**Notes:**
- The existing `providers/` pattern is good. If `yfinance` becomes a problem later, add or swap providers behind the service boundary.
- Broad S&P 500 work should be deterministic, cached, and tolerant of provider failures.
- Agentic/token-heavy reasoning should be reserved for narrowed candidates.
- Candidate context should preserve timing and stage data for the 2-100 day swing-trading goal and future self-learning/attribution.
