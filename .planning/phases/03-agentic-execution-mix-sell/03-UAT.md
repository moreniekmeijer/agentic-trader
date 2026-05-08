---
status: complete
phase: 03-agentic-execution-mix-sell
source: 03-01-SUMMARY.md, 03-02-SUMMARY.md
started: 2026-05-08T09:12:34Z
updated: 2026-05-08T13:44:23Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Execution Worker Flow
expected: Start the worker from a clean process with valid env. The startup sequence should run without schema or import errors, execute the scanner/trade warm-up, instantiate PnL sync, reconciliation, and position review jobs, then reach scheduler startup.
result: pass

### 2. Protected Bracket Entry
expected: When a BUY decision passes risk checks, Alpaca Paper should receive a bracket order, not a plain market buy. The order should have a parent entry plus take-profit and stop-loss legs.
result: pass

### 3. Local Bracket Persistence
expected: After a protected BUY is submitted, the local trade row should store the parent Alpaca order ID, take-profit order ID, stop-loss order ID, take-profit price, and stop-loss price. A `bracket_submitted` event should also be recorded.
result: pass

### 4. Position Review De-Risk Replacement
expected: With an existing long position and bracket legs, the position review job should read current Alpaca positions, produce a conservative de-risk action when technicals turn negative, replace the relevant child leg, and update the local active leg ID/price.
result: pass

### 5. Invalid Or Mismatched Review Safety
expected: If review output would loosen risk or Alpaca/local position state does not match, the job should record a rejection or `state_mismatch` event and should not call Alpaca replacement blindly.
result: pass
fixed: "Fresh DB/container restart exposed duplicate Alpaca client_order_id values; fixed by generating bounded, traceable IDs from symbol, decision id, and decision timestamp. Position-review safety guardrails are covered by tests/test_position_review.py."

### 6. Scheduled Position Review
expected: The worker scheduler should include `PositionReviewJob.run` using `POSITION_REVIEW_INTERVAL`, while startup should not run position review immediately before the scheduler begins.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
