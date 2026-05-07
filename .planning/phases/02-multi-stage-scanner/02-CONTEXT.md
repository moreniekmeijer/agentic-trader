# Phase 02: Multi-Stage Scanner - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Replacing the current hardcoded, deterministic shortlist scan with a staged scanner pipeline:
- a weekly fundamentals pass builds a `Quality Universe`
- a daily technical pass narrows that to an `Active Shortlist`
- a sentiment/news pass adds agent-style context before the downstream discussion/execution layer

This phase clarifies how scanning becomes agentic. It does not yet change execution mechanics like bracket orders or profit-taking logic.

</domain>

<decisions>
## Implementation Decisions

### Scanner Funnel Shape
- **D-01: Universe Source** — Keep the source universe restricted to the `S&P 500` for Phase 2.
- **D-02: Fundamentals Output Size** — The weekly fundamentals stage should output a `top 30` Quality Universe for now.
- **D-03: Technical Directionality** — The daily technical stage is `long-only`; it should surface entry candidates, not bearish/sell ideas.
- **D-04: Sentiment Role** — The sentiment stage is a `soft input`, not a hard gate. It should influence downstream discussion rather than remove symbols outright.

### Agentic Scanner Behavior
- **D-05: Sentiment Output Shape** — The sentiment stage should return an agent-style response, similar in spirit to `AgentResponse`: score/confidence plus reasons.
- **D-06: Worker Evolution** — `worker.py` should evolve toward an orchestrator of distinct scanner stages and cadences, rather than a single flat shortlist loop.
- **D-07: Boundary Model** — Providers/services produce facts, evaluators/agents produce judgment-shaped outputs, scanner stages rank/filter candidates, and `trade_job` remains mostly deterministic.
- **D-08: Candidate Context Spine** — Scanner outputs should be enriched candidate objects, not just symbols or compressed votes. They must preserve timing snapshots, fundamentals, sentiment, stage scores, reasons, and freshness timestamps.
- **D-09: Provider Swappability** — Keep `yfinance` behind provider/service boundaries. If Yahoo throttling or quality becomes a problem, add another provider rather than changing scanner/trade semantics.
- **D-10: Token / API Budget Discipline** — Broad stages should be deterministic and cache-friendly. Agent-style reasoning should be reserved for narrowed candidates, especially the Active Shortlist.

### Phase Boundary Clarification
- **D-11: Agentic Layer in Phase 2** — The scanner itself becomes more agentic in this phase, but final trade discussion/execution remains downstream and is not replaced.
- **D-12: Naming Direction** — Keep existing `Agent` names for now, but treat technical/fundamental/sentiment components as evaluator-style judgment producers. A later rename to `Evaluator`, `SignalAgent`, `DecisionSynthesizer`, or `SignalAggregator` can happen once the boundaries are proven.

### the agent's Discretion
- Exact persistence format for the Quality Universe / Active Shortlist.
- Whether sentiment data is stored directly in worker state, DB tables, or derived transiently before discussion.
- Exact cadence split between weekly fundamentals refresh and daily technical shortlist refresh.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current Worker / Scanner Flow
- `agentic_trader/worker/worker.py` — Current APScheduler orchestration and flat shortlist flow.
- `agentic_trader/scanner/engine.py` — Current deterministic scanner scoring and ranking behavior.
- `agentic_trader/worker/scan_state.py` — Current in-memory worker state for shortlist and fundamentals cache.

### Existing Agents / Services
- `agentic_trader/agents/fundamental/agent.py` — Existing fundamentals scoring agent.
- `agentic_trader/agents/technical/agent.py` — Existing technical signal generation.
- `agentic_trader/agents/discussion/agent.py` — Current weighted discussion layer that should remain downstream.
- `agentic_trader/services/fundamentals/fundamentals_engine.py` — Current fundamentals fetching flow.
- `agentic_trader/services/fundamentals/providers/yahoo_finance.py` — Yahoo fundamentals provider.

### Project Specs
- `.planning/ROADMAP.md` — Phase 2 scope and success criteria.
- `.planning/REQUIREMENTS.md` — `SCAN-01` to `SCAN-04`.
- `.planning/codebase/ARCHITECTURE.md` — Current worker/scanner architecture map.
- `.planning/codebase/CONCERNS.md` — Existing scanner concerns, including deterministic scan limitations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FundamentalsAgent` already encapsulates fundamentals-oriented reasoning and can likely be repurposed for Quality Universe ranking.
- `TechnicalAgent` and the current market-data stack already provide the building blocks for a long-only shortlist stage.
- `WorkerState` already holds shortlist symbols and fundamentals snapshots, so it can likely be extended to represent multi-stage scanner outputs.
- Existing `providers/` folders are the correct place to keep data-source adapters. Future non-yfinance providers should plug in there without reshaping scanner semantics.

### Established Patterns
- APScheduler-based staged jobs already exist in `worker.py` and can be split more intentionally by cadence.
- Agent outputs already flow through shared response models and the downstream `DiscussionAgent`.
- Yahoo Finance is the current source for both market data and fundamentals, so Phase 2 should preserve that constraint unless explicitly deferred.

### Known Concerns To Respect
- Current scanner logic conflates buy and sell strength; Phase 2 should correct this by making the shortlist long-only.
- The current scan universe is hardcoded and small; Phase 2 keeps S&P 500 as the scope boundary but should make the funnel architecture ready for that universe explicitly.
- yfinance is useful but unofficial and fragile. Phase 2 should cache aggressively, tolerate partial provider failures, and avoid API-heavy broad agent loops.
- Future attribution requires preserving raw context and stage scores, not only final `BUY`/`HOLD`/`SELL` outputs.

</code_context>

<specifics>
## Specific Ideas

- Weekly → daily staging should be visible in the worker flow, so the future worker feels like an orchestrated funnel rather than one generic scan step.
- Sentiment should enrich candidate evaluation with confidence and reasons, but should not veto names by itself in Phase 2.
- The scanner's main product should be `CandidateContext` or an equivalent enriched model that downstream execution and later learning can consume.

</specifics>

<deferred>
## Deferred Ideas

- Using scanner-stage outputs to directly generate sell/avoid signals is deferred; Phase 2 shortlist remains long-only.
- Broader universes beyond the S&P 500 are deferred.
- Larger execution-layer orchestration changes beyond scan staging belong to later phases.

</deferred>

---

*Phase: 02-multi-stage-scanner*
*Context gathered: 2026-05-07*
