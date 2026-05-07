---
phase: 02
slug: 02-multi-stage-scanner
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-07
register_authored_at_plan_time: false
---

# Phase 02 — Security

> Retroactive STRIDE review for the multi-stage scanner and sentiment enrichment flow.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Worker env/config | Runtime env variables control scanner sizes and job cadences. | Non-secret operational config |
| External market/fundamentals providers | yfinance-backed providers supply market and fundamentals facts. | Public market data and fundamentals |
| Sentiment provider boundary | Sentiment service can later call a real news/social provider; Phase 02 uses a neutral null provider. | Public sentiment facts, score, confidence, reasons |
| Scanner state to trade execution | In-memory `CandidateContext` moves evaluator outputs into discussion and decision execution. | Symbols, scores, reasons, market/fundamentals snapshots |
| Worker logs | Operational logs expose stage progress, symbols, and aggregate vote summaries. | Non-secret ticker symbols and scores |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-02-01 | Spoofing / Tampering | Scanner universe | mitigate | Universe source is the internal S&P 500 list; `SCAN_UNIVERSE_LIMIT` can only slice the curated list and cannot inject symbols. Active shortlist derives only from Quality Universe candidates. | closed |
| T-02-02 | Tampering / DoS | External provider data | accept / mitigate | yfinance integrity/availability is accepted for paper-trading v1; mitigations include provider abstraction, per-symbol failure tolerance, empty-frame guards, freshness checks, and Alpaca/database as execution source of truth. | closed |
| T-02-03 | DoS | Scanner env config | mitigate | Scanner sizes and scheduler cadences are bounded via `_env_int(..., min_value/max_value)`; invalid/out-of-range values fall back to safe defaults. Covered by `test_env_int_enforces_config_bounds`. | closed |
| T-02-04 | Information Disclosure | Secrets and logs | mitigate | `.env.example` contains no secrets; worker does not log env values or Alpaca credentials; stage logs expose only ticker symbols, scores, and non-secret status. | closed |
| T-02-05 | Tampering / Repudiation | Candidate context to trade execution | mitigate | Candidate context is stored in thread-safe worker state; trade flow deduplicates evaluator responses, uses scanner-provided votes where available, and persists decisions/trades through existing repository paths. | closed |
| T-02-06 | Elevation / Business Logic Abuse | Sentiment enrichment | mitigate | Sentiment is soft input only: enrichment cannot add symbols or remove candidates. Default `NullSentimentProvider` emits neutral score/confidence, and discussion weight is limited to 0.1. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02-02 | yfinance is an unofficial public-data provider. Accepted for paper-trading v1 because this phase keeps it behind provider abstractions, tolerates per-symbol failures, and can swap providers later without reshaping scanner boundaries. | Project owner / Phase 02 architecture discussion | 2026-05-07 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-07 | 6 | 6 | 0 | Codex inline security audit |

---

## Verification Evidence

- `agentic_trader/worker/worker.py` bounds scanner size/cadence env config and keeps sentiment after shortlist generation.
- `agentic_trader/worker/scan_state.py` keeps scanner updates under a lock and updates sentiment only over existing active candidates.
- `agentic_trader/services/fundamentals/fundamentals_engine.py` and `agentic_trader/services/sentiment/sentiment_engine.py` tolerate per-symbol provider failures.
- `agentic_trader/scanner/engine.py` builds Quality Universe and Active Shortlist from staged inputs rather than arbitrary runtime symbols.
- `tests/test_worker_runtime_guards.py` covers env config bounds.
- `tests/test_scanner_pipeline.py` covers long-only shortlist behavior, sentiment output shape, sentiment non-removal, and candidate-context trade consumption.
- `zsh -lic 'make'` passed: Ruff, ty, and 13 tests.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-07
