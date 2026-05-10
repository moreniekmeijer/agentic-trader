# Release Notes: Strategic Agentic Trading Transition

This update marks the complete evolution from a prototype 5-minute polling bot to an autonomous, event-driven **Strategic Fund Manager**.

## Core Architectural Shifts
- **Strategic vs. Tactical**: Decision-making is now a once-daily "Strategic" event, while execution is handled by Alpaca's matching engine via "Tactical" Bracket Orders.
- **Event-Driven Bus**: The worker has been refactored to use an `EventBus`, making the pipeline modular and asynchronously reactive.
- **Database Persistence**: State management (shortlists, fundamentals, market states) has been migrated from local JSON files to a robust Postgres database.

## New Features
- **Bracket Orders (OCO)**: Trades now include automated `limit_price`, `stop_loss_price`, and `take_profit_price` sent as a single atomic unit.
- **Portfolio Review Layer**: Added a daily review cycle where a `PortfolioAgent` analyzes open positions against their original thesis to decide on early exits.
- **Volatility-Aware AI**: Integrated **ATR (Average True Range)**. The technical agent now provides volatility context, allowing the LLM to set mathematically sound price targets.
- **Conviction Risk Engine**: Position sizing is now determined by LLM conviction (Low: 0.5%, Medium: 1%, High: 2% risk) and automatically capped by current account buying power.

## Cleanup & Refactoring
- **Deprecated Code Removal**: Deleted the old `DiscussionAgent`, `scan_state.py`, and `pnl_sync.py`.
- **Alpaca Controller**: Streamlined API interactions, removing unused legacy market order methods.
- **Import Optimization**: Performed a full audit and cleanup of unused imports across the codebase.

## Key Bug Fixes
- **DB Integrity**: Fixed `NotNullViolation` on trade prices by providing intended price fallbacks for pending bracket orders.
- **Buying Power Safety**: Implemented strict caps on share quantity to prevent "Insufficient Buying Power" errors.
- **ATR Stability**: Resolved `NoneType` attribute errors during market data computation.

---
*Status: System is now fully autonomous and risk-aware.*
