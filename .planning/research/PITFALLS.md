# Research: Pitfalls & Risk Mitigation

## Lookahead Bias (The "Future Information" Trap)

**The Risk**: Using information that wouldn't have been available at the decision time (e.g., using a stock's closing price for a trade made at the opening).

### Mitigations:
1.  **Strict Temporal Partitioning**: Ensure training/backtesting data is strictly chronological. Never shuffle time-series data.
2.  **Point-in-Time Data**: Use data providers (like Alpaca) that offer PiT historical data (adjusting for splits/dividends only as they occurred).
3.  **Audit Feature Engineering**: Ensure rolling windows and indicators (RSI, MA) only use data points $t < \text{decision time}$.

## Data Leakage

**The Risk**: Information from the test set "leaking" into the training process (e.g., global scaling/normalization based on the entire dataset).

### Mitigations:
1.  **Pipeline Isolation**: Normalize and scale data using statistics calculated **only** on the training subset.
2.  **Feature Pruning**: If a feature shows near-perfect correlation with the outcome, it is likely leaking future information.

## Sentiment Noise & Hallucination

**The Risk**: LLMs misinterpreting news sentiment or "hallucinating" financial facts.

### Mitigations:
1.  **Sentiment Verification**: Use multiple sentiment providers (e.g., specialized BERT models + LLM) and only act when they agree.
2.  **Noise Filtering**: Sentiment should be a **secondary filter**, not a primary driver. A fundamental/technical setup must exist first.
3.  **Confidence Thresholds**: Agents should return a "Low Confidence" score if the news text is ambiguous or lacks clear sentiment.

## Self-Learning Overfitting

**The Risk**: The system "learning" from random market noise (e.g., "The Technical agent is good because it won 3 trades in a row during a bull market").

### Mitigations:
1.  **Bayesian Prior**: Start with strong hardcoded priors (weights) and allow them to change only slowly.
2.  **Regime Awareness**: Tag trades with the market regime (Bull/Bear/Sideways). A signal might work in Bull markets but fail in Sideways markets.
3.  **Complexity Penalty**: Prefer simpler attribution models. Don't try to find "the perfect indicator combination" for every single trade.
