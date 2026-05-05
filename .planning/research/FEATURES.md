# Research: Features & Agentic Learning

## P&L Attribution & Learning

The core of a self-learning system is the ability to attribute outcomes (P&L) back to specific signals while filtering out market noise.

### Attribution Strategy:
1.  **Signal Snapshotting**:
    *   At the moment of decision, capture the **full vector** of inputs: RSI, MA crossovers, Fundamentals scores, Sector momentum, and Agent confidence levels.
    *   Store this in the `decisions` table as a `signal_snapshot`.
2.  **Attribution Agents**:
    *   Create a specialized agent that periodically (daily/weekly) reviews closed trades.
    *   Compare the `signal_snapshot` with the `realized_pnl`.
    *   **Goal**: Identify which agents were "right" (correlated with profit) in specific market regimes.
3.  **Bayesian Weight Updating**:
    *   Instead of hardcoded weights (0.7 Technical, 0.3 Fundamental), adjust weights dynamically based on recent attribution performance.
    *   *Example*: If Technical signals have been 80% accurate over the last 10 trades, increase their weight slightly.

## Advanced Scanning

The current scan job is a simple RSI/Volume filter. A more agentic approach involves a multi-stage funnel.

### Funnel Stages:
1.  **Stage 1: Fundamental Quality (Weekly)**:
    *   Filter the S&P 500 for "Quality" (ROE > 15%, Debt/Equity < 0.5, Growing margins).
    *   Output: "Quality Universe" (e.g., 50-100 stocks).
2.  **Stage 2: Technical Timing (Daily)**:
    *   Scan the Quality Universe for "Setups" (RSI oversold on 4h, Bullish engulfing, etc.).
    *   Output: "Active Shortlist" (e.g., 10-20 stocks).
3.  **Stage 3: Sentiment/News (Real-time/Event-driven)**:
    *   Check for recent earnings, news sentiment, or social spikes on the shortlist.
    *   Output: "Discussion Candidate".

## Oversight & Dashboard

*   **Feedback Loop**: Implement a "Mark as Bad Trade" manual flag in the UI.
*   **Reasoning**: If a user marks a trade as bad (e.g., "Good technicals but bad news I knew about"), the Attribution Agent should penalize that specific signal combination.
