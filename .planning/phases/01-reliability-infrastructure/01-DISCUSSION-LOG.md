# Phase 01: Reliability & Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 01-reliability-infrastructure
**Areas discussed:** Worker Failure Recovery, Persistence, Synchronization, Idempotency, Deployment Target

---

## Worker Failure Recovery & Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Stateless Worker | Re-scan and re-fetch on every startup. | |
| Full DB Persistence | Save everything (including DataFrames) to DB. | |
| Hybrid Persistence | Save watchlist and heartbeat to DB; re-fetch price history on restart. | ✓ |

**User's choice:** Hybrid Persistence.
**Notes:** User agreed that for local dev on a laptop, being able to resume the watchlist is critical, while re-fetching price data ensures freshness and reduces DB bloat.

---

## Synchronization Strategy (Alpaca → DB)

| Option | Description | Selected |
|--------|-------------|----------|
| Polling-based | Regular polling of Alpaca activities API. | ✓ |
| Event-based | Webhooks/Streaming for real-time updates. | |

**User's choice:** Polling-based.
**Notes:** Polling was chosen because it is "catch-up friendly" for a laptop that is periodically offline and doesn't require a stable public endpoint. Cadence shortened to 1-5 minutes.

---

## Deployment Target

| Option | Description | Selected |
|--------|-------------|----------|
| Local Dev only | Focus on laptop-only reliability. | |
| Remote VPS | Always-on cloud deployment. | |
| Cloud-Ready Local | Build as if always-on, but run locally for now. | ✓ |

**User's choice:** Cloud-Ready Local.
**Notes:** User emphasized that we should build for always-on resilience (persistence + idempotency) while still testing/running in local dev mode.

---

## the agent's Discretion

- Specific implementation of SQL heartbeats.
- Serialization logic for the persistent watchlist.

## Deferred Ideas

- **Temporal/Celery**: Gold standard for reliability, but deferred to v2.
- **Webhooks**: Deferred to avoid local tunnel/public endpoint complexity.
