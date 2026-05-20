# Architecture Analysis & Overlapping Responsibilities

Overall, the `agentic-trader` architecture is highly robust. The separation between deterministic rule engines (like `TechnicalAgent` and `RiskEngine`) and stochastic LLM reasoning (like `SynthesizerAgent`) is a fantastic design pattern that protects capital from AI hallucinations. The "Learning Loop" (Reflector) is also a standout feature. 

However, as the system has evolved, a few overlapping responsibilities and areas of friction have emerged.

## 1. The "Risk & Validation" Overlap

There are three distinct components currently guarding the execution layer:
1. `PortfolioManager.validate()` (Alters the LLM's decision back to `HOLD` if rules fail)
2. `DecisionEngine.execute_decision()` (Drops the trade if an open order exists, limits are hit, or bracket calculation fails)
3. `RiskEngine.can_trade()` (Rejects the trade if cash, cooldown, or max position limits are hit)

**The Overlap**:
- Both `PortfolioManager` and `DecisionEngine` check for open broker orders.
  - `PortfolioManager._has_open_order()` checks open orders to append a reason: *"Broker already has an open order for this symbol."*
  - `DecisionEngine` checks `self.executor.has_open_orders(symbol)` and will independently block the intent if `PortfolioManager` misses it.
- `PortfolioManager` checks if we already have a position to determine if a `REDUCE` or `EXIT` signal is valid.
- `RiskEngine` checks `positions` to see if we've hit `max_total_positions`.

**Recommendation**: 
Consolidate all broker-state validation into the `RiskEngine`. `PortfolioManager` should solely validate the *LLM's internal logic* (e.g., "Did it provide an invalidation thesis? Is it ignoring a hard fundamental sell?"). Checking active broker state (open orders, cash, active positions) should be exclusively handled downstream by the `RiskEngine` and `DecisionEngine`.

## 2. Market Data Retrieval (Redundant API Calls)

The system currently runs through multiple passes of the same symbols, which causes duplicate data fetching.

**The Overlap**:
- `ScannerEngine.scan()` fetches `provider.get_bars(symbol)` for all monitored symbols to find the top 10.
- Immediately after, `handle_batch_analysis()` runs. For those same 10 symbols, it calls `provider.get_bars(symbol, interval="1d")` and `provider.get_bars(symbol, interval="4h")` again.
- Later, `PositionReviewService` fetches `df_daily` and `df_4h` *again* for any open positions.

**Recommendation**:
Implement an in-memory caching layer or pass the computed `MarketDataSnapshot` down through the Event Bus. Since the `ScannerEngine` already downloads the Daily bars, those dataframes should be cached locally for the duration of the trading cycle so `handle_batch_analysis` doesn't incur additional latency or rate-limiting risks from Yahoo Finance.

## 3. Database Query Leakage (Repository Pattern vs Handlers)

The system introduces a `database/repositories/` folder to centralize queries (e.g., `TradeRepository`, `OrderIntentRepository`).

**The Overlap**:
While `DecisionEngine` neatly uses `TradeRepository` and `OrderIntentRepository`, the `worker/handlers/` and background services often bypass the repositories and write raw SQLAlchemy queries.
- `handle_batch_analysis` directly queries `FundamentalsData`.
- `handle_scan_triggered` directly queries `MarketState`.
- `PositionReviewService` directly queries `PositionLifecycle` (`self.session.query(PositionLifecycle)`).

**Recommendation**:
Strictly enforce the Repository Pattern. Create a `MarketStateRepository` and a `PositionLifecycleRepository`. This will make the handlers significantly easier to unit test, as you can mock the repository interfaces rather than dealing with SQLite/Postgres sessions in tests.

## 4. Local PnL Sync vs Broker Truth

The `FillPnLSync` service performs a complex matching algorithm: taking raw Alpaca fills, grouping them by `order_id`, matching sells to oldest open buys, and computing a local PnL.

**The Friction**:
Alpaca natively tracks Unrealized and Realized PnL at the position level. Attempting to rebuild PnL manually via FIFO (First In, First Out) lot matching locally is notoriously fragile (e.g., partial fills across multiple days, manual interventions on the broker side, corporate actions like splits). 

**Why it exists**: You need this local mapping because you are tying specific financial outcomes back to the exact LLM `Decision` ID for the `ReflectorAgent` to learn from. 

**Recommendation**:
Keep the `FillPnLSync` for linking LLM decisions to outcomes, but rely on Alpaca's `Position` endpoint for actual risk math. The current implementation looks solid, but be aware that any manual trading on the Alpaca account will permanently desync the local database's logic for closing trades.

## 5. Worker Simplicity and Structure

**The Current Structure**:
The `worker/` directory is currently a mix of infrastructure code (like `worker.py`, `context.py`, `scheduler.py`, `registry.py`) and business logic services (like `pnl_sync.py` and `position_review.py`). Furthermore, the `factories.py` file, which is a dependency injection container, sits alongside event handlers.

**The Friction**:
- Business logic is mingling with infrastructure. `position_review.py` and `pnl_sync.py` are standalone services but are dumped in the root of the `worker/` directory. 
- The `worker/handlers/` module is relatively clean, but it acts as a secondary "services" layer because the handlers themselves hold significant orchestration logic instead of just routing events to dedicated service classes.

**Recommendation**:
- Move `pnl_sync.py` into a dedicated `execution/` or `services/` directory.
- Move `position_review.py` into `services/portfolio/`.
- Extract the orchestration logic out of the `worker/handlers/` and into standalone service classes (e.g., an `ArenaService` or `TradingCycleService`). The `worker` directory should be stripped down strictly to infrastructure: starting the loop, configuring dependencies, and routing events to external services.

## 6. Alpaca vs. Database Responsibilities (Source of Truth)

**The Current Structure**:
The database schema (`models.py`) defines `OrderLifecycle` and `PositionLifecycle` tables. These tables track the open position quantity, average entry price, current price, unrealized PnL, and status, effectively mirroring Alpaca's live broker state.

**The Friction (Overlap in DB Schemas)**:
- **Alpaca is the Source of Truth**: Alpaca inherently tracks live position values, average entry prices, and open orders. Replicating `current_price` and `unrealized_plpc` inside the local `PositionLifecycle` table creates synchronization headaches and a leaky abstraction. If the bot crashes for a day, the local DB becomes stale while Alpaca holds the true state.
- **Why it exists**: The DB schemas currently mirror Alpaca because the system needs to persist the LLM's initial thought process (`thesis`, `invalidation`, `expected_horizon_days`) alongside the active position. Since Alpaca's API doesn't allow attaching custom LLM metadata to a position, the bot forces a local copy of the position to hold this metadata.

**Recommendation**:
- **Decouple the Metadata from the Live State**: Instead of mirroring the entire position in `PositionLifecycle`, convert this table into a `PositionMeta` table. It should solely store `symbol`, `decision_id`, `thesis`, `invalidation`, and `expected_horizon_days`. 
- **Fetch on Demand**: When `PositionReviewService` runs, it should fetch the *live* `Position` object directly from Alpaca (the absolute source of truth for PnL and qty), and simply query the database for the matching `PositionMeta` to retrieve the LLM's original thesis. This removes the need to constantly sync `current_price` and `unrealized_pl` into Postgres, cleanly separating "Live Broker State" from "Local AI Context".

## Summary

The architecture is excellent, particularly the `Agentic` pipeline. To mature the system, focus on:
1. **Removing Broker State from PortfolioManager**.
2. **Caching `yfinance` Dataframes per trading cycle**.
3. **Consolidating SQLAlchemy queries into the Repositories**.
4. **Stripping the Worker directory down to pure routing infrastructure**.
5. **Decoupling LLM Thesis metadata from Live Alpaca state to prevent schema overlap**.
