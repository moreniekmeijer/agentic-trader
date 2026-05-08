# Phase 03: Agentic Execution (Mix Sell) - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase turns successful entry decisions into protected Alpaca bracket orders and adds an agentic open-position review loop for exit management.

In scope:
- BUY entries are submitted as Alpaca bracket orders with initial stop-loss and take-profit legs.
- Existing long positions are periodically re-evaluated for early exit or bracket leg tightening.
- Existing bracket legs can be modified via Alpaca order replacement when the system decides to de-risk.
- Local persistence stores enough order identity and adjustment history to manage the active bracket and support later attribution.

Out of scope:
- Short selling.
- Agent-selected entry prices or discretionary limit-entry pricing.
- Phase 4 attribution, Bayesian weight updates, or self-learning logic beyond preserving useful execution context.
- Expanding the scanner universe or changing Phase 2 scanner semantics.

</domain>

<decisions>
## Implementation Decisions

### Execution Semantics
- **D-01: Long-only execution** - `BUY` may open or increase a long position. `SELL` may only close or reduce an existing long position. `SELL` with no owned/available quantity is blocked or no-op. The system must never open short positions in v1.
- **D-02: Deterministic trade job** - `trade_job` should become a thin orchestration path: consume enriched scanner candidates, run final synthesis, apply risk checks, submit orders, and persist results. Agents/evaluators provide conviction, timing context, confidence, and reasons; they do not choose the exact buy price.
- **D-03: Market bracket entries** - Initial entries remain market-style execution through Alpaca. Alpaca determines actual fill price. Bracket leg prices are derived deterministically from the latest trusted market reference, then reconciliation/sync can refresh actual fill details.
- **D-04: Separate position review** - Agentic exit management should live in a dedicated open-position review flow, expected as a separate scheduled job such as `position_review_job`. It should review current Alpaca positions, not only symbols in the current scanner shortlist.

### Bracket Policy
- **D-05: Brackets are mandatory for entries** - Every accepted `BUY` entry order must include Alpaca stop-loss and take-profit protection.
- **D-06: Volatility-aware default levels** - Initial stop-loss and take-profit prices should be based on daily volatility/ATR-style distance with sane minimum and maximum bounds. If required volatility data is unavailable, fall back to simple fixed percentages.
- **D-07: Approximate 2R default reward/risk** - The first take-profit target should default to roughly twice the initial risk distance. This is a starting safety policy, not a learned strategy.
- **D-08: Stop as hard floor, target as default ceiling** - The stop-loss leg is the mechanical downside guard. The take-profit leg is the default mechanical upside target that may later be lowered by the agentic review flow.

### Agentic Exit Authority
- **D-09: Agents may only de-risk** - The agentic review flow may tighten a stop, lower a take-profit target, or request an early close/reduction. It may not loosen a stop, widen downside risk, or otherwise increase risk exposure.
- **D-10: No target expansion in Phase 3** - Raising take-profit targets or otherwise extending upside discretion is deferred. Phase 3 focuses on protected entries and conservative exit adjustments.
- **D-11: Alpaca remains source of truth** - Before replacing bracket legs, the system must use Alpaca order/position state as authoritative. If local bracket IDs are missing or inconsistent, the safe behavior is to refresh from Alpaca, log the mismatch, and avoid blind modification.

### Persistence Depth
- **D-12: Minimal operational fields** - Store only the active Alpaca identifiers required to manage the trade and its bracket, such as parent/order ID and current stop-loss/take-profit leg IDs. Do not add speculative columns that are not used by execution, reconciliation, or planning-approved learning needs.
- **D-13: Event trail for actual changes** - Keep an append-only event/adjustment record only when the system actually places, replaces, cancels, closes, or repairs bracket-related orders. This should preserve enough context for audit and Phase 4 learning without mirroring every Alpaca field locally.
- **D-14: Model alignment first** - Database models, mappers, repositories, and API/read models must stay aligned. If a field is persisted, it needs a clear read/write owner and test coverage.

### the agent's Discretion
- Exact ATR/min/max formulas and fallback fixed percentages, as long as they are conservative, testable, and configurable enough for paper trading.
- Exact name and shape of the bracket event table/model, as long as it is minimal and records real order lifecycle changes.
- Whether the position review job reuses existing discussion/evaluator models directly or introduces a small exit-specific response model, as long as boundaries remain clear.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Scope
- `.planning/ROADMAP.md` - Phase 3 goal, requirements, success criteria, and plan split.
- `.planning/REQUIREMENTS.md` - `EXEC-01`, `EXEC-02`, and `EXEC-03` execution requirements.
- `.planning/PROJECT.md` - Project-level decisions: Alpaca as source of truth, paper trading, mix sell logic, and swing-trading context.
- `.planning/STATE.md` - Current project state, pending todos, and known follow-up hardening.
- `.planning/research/ARCHITECTURE.md` - Bracket coordination pattern and source-of-truth notes.
- `.planning/phases/02-multi-stage-scanner/02-CONTEXT.md` - Scanner boundary model and enriched `CandidateContext` decisions that feed execution.

### Execution And Alpaca Integration
- `agentic_trader/decision/engine.py` - Current decision-to-order orchestration and persistence path.
- `agentic_trader/controller/alpaca_controller.py` - Current Alpaca wrapper; bracket and replace-order operations belong here or behind this boundary.
- `agentic_trader/risk/engine.py` - Existing confidence, cooldown, quantity, and max-position guards.
- `agentic_trader/worker/worker.py` - Scheduler jobs, trade loop, and future integration point for position review.
- `agentic_trader/worker/reconciliation.py` - Current Alpaca/local position reconciliation behavior.
- `agentic_trader/worker/pnl_sync.py` - Current fill/PnL synchronization behavior.

### Persistence And Candidate Context
- `agentic_trader/database/models.py` - Current `Decision`, `Trade`, `AgentVote`, and heartbeat models.
- `agentic_trader/database/mapper.py` - Current mapping helpers between Alpaca/domain objects and ORM models.
- `agentic_trader/database/repository.py` - Current repository layer used for decisions, trades, and worker state.
- `agentic_trader/scanner/models.py` - `CandidateContext` shape created in Phase 2 and consumed by the trade flow.
- `agentic_trader/agents/models.py` - Current `AgentResponse` and `AggregatedResponse` response shapes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DecisionEngine` already owns the boundary between an aggregated decision, risk gate, Alpaca order submission, and trade persistence.
- `AlpacaController` already centralizes symbol normalization, order placement, position reads, and open-order checks.
- `RiskEngine` already provides max position sizing and confidence guards that can remain deterministic around bracket entries.
- `CandidateContext` already carries market, fundamentals, sentiment, scores, and evaluator responses from the scanner into the trade flow.
- `ReconciliationJob` and `PnlSyncJob` already establish the pattern that Alpaca is authoritative and local DB state is synced afterward.

### Established Patterns
- Worker jobs are APScheduler functions in `agentic_trader/worker/worker.py`; Phase 3 should add exit review as another clear job rather than overloading scanner stages.
- Provider/service/evaluator boundaries from Phase 2 should continue: facts and market references remain outside the execution layer, while execution stays deterministic.
- Persistence currently uses SQLAlchemy models plus mapper/repository helpers. New bracket/order state should follow that pattern rather than writing ad hoc fields from worker code.
- The app is paper-trading only for v1. Phase 3 should preserve that safety stance.

### Integration Points
- `DecisionEngine._execute_trade()` is the likely entry point for changing `BUY` from simple market order to protected bracket order.
- `AlpacaController.place_market_order()` / `buy()` / `sell()` need bracket-aware companions and replace-order support.
- `Trade` persistence needs active bracket identifiers and an event trail for actual order lifecycle changes.
- A new scheduled open-position review job should connect Alpaca positions, local trade/bracket state, current market context, and conservative exit decisions.

</code_context>

<specifics>
## Specific Ideas

- Phase 3 should keep the execution layer clean: scanner/evaluators decide whether a name is interesting, while execution decides quantity and protective mechanics.
- The trade flow should not let agents choose exact buy prices in v1.
- Persistence should be minimal and model-aligned: operational IDs on the active trade, plus append-only events for real bracket/order changes.
- The 2-100 day swing-trading goal favors daily-volatility brackets and hourly/periodic position review rather than intraday reaction logic.

</specifics>

<deferred>
## Deferred Ideas

- Agent discretion to raise take-profit targets or extend winners.
- Limit-entry pricing selected by agents.
- Short selling or bearish scanner-driven entries.
- Full Phase 4 attribution and Bayesian learning, beyond preserving execution context needed later.

</deferred>

---

*Phase: 03-agentic-execution-mix-sell*
*Context gathered: 2026-05-08*
