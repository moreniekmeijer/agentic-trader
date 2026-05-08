# Phase 03: Agentic Execution (Mix Sell) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 03-agentic-execution-mix-sell
**Areas discussed:** Bracket policy, agent exit authority, review cadence, long-only semantics, persistence depth, trade-job boundary

---

## Bracket Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed percentages | Use simple fixed stop-loss and take-profit percentages for all entries. | |
| Volatility-aware brackets | Use daily volatility/ATR-style levels with min/max bounds and fixed-percentage fallback. | yes |
| Fully signal-based brackets | Let agent/signal logic choose each bracket level case by case. | |

**User's choice:** Proceed with proposed defaults.
**Notes:** The selected default favors volatility-aware bracket levels, approximately 2R take-profit, and fixed-percentage fallback if market data is missing.

---

## Agent Exit Authority

| Option | Description | Selected |
|--------|-------------|----------|
| De-risk only | Agents may tighten stops, lower targets, or close early; they cannot increase downside risk. | yes |
| Full bracket discretion | Agents may move stop-loss and take-profit in either direction. | |
| Mechanical only | No agentic bracket changes; rely only on initial brackets. | |

**User's choice:** Proceed with proposed defaults.
**Notes:** The exit layer should be conservative in Phase 3. Raising targets or loosening risk is deferred.

---

## Review Cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Separate position review job | Add a scheduled open-position review job, defaulting around hourly, independent of scanner shortlist membership. | yes |
| Fold into trade_job | Evaluate entries and open-position exits inside the same trade cycle. | |
| Manual-only review | Place brackets but do not automatically revisit bracket legs yet. | |

**User's choice:** Proceed with proposed defaults.
**Notes:** A separate job keeps the trade entry path smaller and prevents open positions from being ignored when they fall out of the current scanner shortlist.

---

## Long-Only Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Long-only close/reduce | `SELL` may only close or reduce an existing long; never open shorts. | yes |
| Bidirectional trading | `SELL` may open short positions when bearish conviction is high. | |

**User's choice:** User asked for clarification, then agreed it made sense.
**Notes:** `BUY` opens/increases long exposure. `SELL` with no owned quantity becomes blocked/no-op. This carries forward Phase 2's long-only scanner decision.

---

## Persistence Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Active IDs only | Store only the current Alpaca parent/leg identifiers needed to modify active brackets. | |
| Active IDs plus minimal event log | Store active operational IDs and append events only for real bracket/order lifecycle changes. | yes |
| Full Alpaca mirror | Store a broad local copy of all Alpaca order fields and updates. | |

**User's choice:** User agreed with the event-log idea but emphasized keeping models aligned and not creating/saving extra fields if not needed.
**Notes:** The implementation should avoid speculative schema growth. Any persisted field needs a clear operational or learning purpose and aligned model/mapper/repository/API handling.

---

## Trade-Job Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic execution orchestrator | Agents provide conviction and context; execution handles quantity, bracket levels, submission, and persistence. | yes |
| Agent-selected buy price | Agents decide exact entry prices for each stock. | |
| Monolithic trade job | Keep scanner, discussion, entry execution, and exit management tightly coupled in the same flow. | |

**User's choice:** User asked whether agents would decide buy price; selected the deterministic boundary after clarification.
**Notes:** Alpaca determines market fill price. Bracket levels use a deterministic policy based on trusted market reference data. Agentic behavior is primarily in open-position review and conservative exit adjustment.

---

## the agent's Discretion

- Exact ATR/min/max formulas and fixed fallback percentages.
- Exact schema shape for active bracket IDs and bracket/order event records, as long as the model remains minimal and aligned.
- Exact implementation split between reusing existing agent response models and introducing an exit-specific response model.

## Deferred Ideas

- Agent-selected limit-entry prices.
- Raising profit targets or extending winners.
- Short selling.
- Full attribution/self-learning logic beyond preserving useful execution context.
