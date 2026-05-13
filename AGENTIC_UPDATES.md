# Release Notes: Strategic Agentic Trading Transition

This update marks the complete evolution from a prototype 5-minute polling bot to an autonomous, event-driven **Strategic Fund Manager**.

## Core Architectural Shifts
- **Strategic vs. Tactical**: Decision-making is now a once-daily "Strategic" event, while execution is handled by Alpaca's matching engine via "Tactical" Bracket Orders.
- **Event-Driven Bus**: The worker has been refactored to use an `EventBus`, making the pipeline modular and asynchronously reactive.
- **Database Persistence**: State management (shortlists, fundamentals, market states) has been migrated from local JSON files to a robust Postgres database.

## New Features
- **Bracket Orders (OCO)**: Trades now include automated `limit_price`, `stop_loss_price`, and `take_profit_price` sent as a single atomic unit.
- **News Sentiment Analysis**: Integrated a `SentimentAgent` that processes real-time news headlines. Bypassed Alpaca SDK bugs via a custom direct HTTP News Engine for reliable data acquisition.
- **Arena Mode (Batch Synthesis)**: Transformed the `SynthesizerAgent` into a Batch Portfolio Manager. It now compares the entire shortlist at once, picking the top 3 opportunities based on cross-symbol confluence.
- **Reflection Loop (Automated Learning)**: Implemented a `ReflectorAgent` that analyzes closed trades. Lessons are stored in a `TradeJournal` and provided to the Synthesizer as historical context.
- **Portfolio Review Layer**: Added a daily review cycle where a `PortfolioAgent` analyzes open positions against their original thesis to decide on early exits.
- **Volatility-Aware AI**: Integrated **ATR (Average True Range)**. The technical agent now provides volatility context, allowing the LLM to set mathematically sound price targets.
- **Conviction Risk Engine**: Position sizing is now determined by LLM conviction (Low: 0.5%, Medium: 1%, High: 2% risk) and automatically capped by current account buying power.

## Cleanup & Refactoring
- **Direct HTTP Engine**: Added robust `urllib` based API communication in `AlpacaController` for news fetching.
- **Arena Flow**: Refactored `worker.py` to support `BatchAnalysisRequestedEvent` and `ReflectionTriggeredEvent`.
- **Deprecated Code Removal**: Deleted the old `DiscussionAgent`, `scan_state.py`, and `pnl_sync.py`.

## Key Bug Fixes
- **BaseAgent Thresholds**: Fixed `MissingArgument` error when instantiating agents in batch mode by enforcing explicit buy/sell thresholds.
- **DB Integrity**: Fixed `NotNullViolation` on trade prices by providing intended price fallbacks for pending bracket orders.
- **Buying Power Safety**: Implemented strict caps on share quantity to prevent "Insufficient Buying Power" errors.
- **ATR Stability**: Resolved `NoneType` attribute errors during market data computation.

---
*Status: System is now a learning, comparative, and multi-agent competitive environment.*
