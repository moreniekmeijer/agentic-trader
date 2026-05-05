# Agentic Trader

## What This Is

A fully automated agentic trading system built for self-use. The system leverages a multi-agent discussion layer to evaluate swing trading opportunities (days to weeks) based on both technical and fundamental signals.

Alpaca is the primary broker and source of truth for all positions and trades. The system uses a FastAPI layer and a PostgreSQL database to persist decisions, votes, and trade history for performance tracking and agentic learning.

## Context

- **Broker**: Alpaca (Paper Trading)
- **Timeframe**: Swing trading (2-10 days)
- **Data Sources**: Yahoo Finance (Daily/4h bars and Fundamentals)
- **Persistence**: PostgreSQL (SQLAlchemy)
- **Execution**: APScheduler-driven worker process

## Core Value

Automate the "heavy lifting" of market scanning and analysis while providing a structured framework for agents to learn from historical outcomes through attribution and signal snapshotting.

## Requirements

### Validated

- ✓ **Multi-timeframe Analysis** — Existing engine for daily and 4h indicators.
- ✓ **Fundamentals Scoring** — Existing agent for financial health checks.
- ✓ **Weighted Discussion** — Decision aggregation via DiscussionAgent.
- ✓ **Alpaca Integration** — Basic paper trading order execution.
- ✓ **Decision Persistence** — Decisions and votes stored in PostgreSQL.
- ✓ **PnL Synchronization** — Backfilling trade outcomes from Alpaca activities.
- ✓ **Read-only API** — FastAPI endpoints for decisions and trade history.

### Active

- [ ] **Continuous Worker Execution** — Stabilize worker to run 24/7 during trading hours.
- [ ] **Advanced Scanning Layer** — Move beyond hardcoded lists to a dynamic agent-driven scanner.
- [ ] **Agentic Sell Logic** — Implement "Mix" logic: Alpaca handles stops (brackets), Agents handle profit targets.
- [ ] **Signal State Snapshotting** — Record full indicator/confidence state at decision time for future learning.
- [ ] **Self-Learning Discussion** — Implement correlation analysis between signal states and P&L outcomes.
- [ ] **News/Sentiment Integration** — Explore adding a sentiment agent to the scanning/decision loop.
- [ ] **Feedback Loop** — Allow manual feedback/labeling of trades to guide agent weight adjustments.

### Out of Scope

- **Intraday Trading** — Streaming data and high-frequency execution are explicitly excluded.
- **Frontend Dashboard** — Post-initialization goal; current focus is on the engine and API.
- **Live Trading** — Restricted to Paper Trading mode for now.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **Swing Timeframe** | Fits Yahoo Finance data and APScheduler cadence; avoids streaming complexity. | Validated |
| **Mix Sell Logic** | Alpaca handles mechanical risk (stops); agents handle subjective value (profit targets). | Active |
| **Alpaca as Source of Truth** | Avoids state desync; DB is for tracking and learning, not core state. | Validated |
| **Snapshotting for Learning** | Enables attribution of profit to specific signal combinations amidst market noise. | Active |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-05 after initialization*
