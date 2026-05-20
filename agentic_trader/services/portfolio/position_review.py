from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agentic_trader.agents.portfolio.agent import PortfolioDecision
from agentic_trader.broker.models import BrokerSnapshot
from agentic_trader.database.models import PositionMeta
from agentic_trader.database.repositories.positions import PositionMetaRepository
from agentic_trader.database.repositories.trades import TradeRepository
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.portfolio.policy import PortfolioPolicy
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.worker.factories import build_trade_pipeline

logger = logging.getLogger(__name__)

_ALLOWED_ACTIONS = {"HOLD", "TIGHTEN_STOP", "REDUCE", "EXIT"}


class PositionReviewService:
    """Review broker-confirmed open positions and record de-risking decisions."""

    def __init__(
        self,
        *,
        session: Session,
        provider: YahooFinanceProvider,
        portfolio_agent: Any,
        decision_engine: DecisionEngine,
        policy: PortfolioPolicy | None = None,
    ):
        self.session = session
        self.provider = provider
        self.portfolio_agent = portfolio_agent
        self.decision_engine = decision_engine
        self.policy = policy or PortfolioPolicy.from_env()
        self.pos_repo = PositionMetaRepository(session)
        self.trade_repo = TradeRepository(session)

    def review_snapshot(self, snapshot: BrokerSnapshot) -> None:
        for position in snapshot.positions:
            decision = self._review_position(position)
            accepted, rejection_reason = self._is_accepted(decision)
            self._record_review(position.symbol, decision, accepted, rejection_reason)

            if accepted and decision.action != "HOLD":
                self.decision_engine.execute_review_decision(decision, position.symbol)

        self.session.commit()

    def _review_position(self, position) -> PortfolioDecision:
        symbol = position.symbol
        meta = self._position_meta(symbol)
        deterministic = self._deterministic_review(position, meta)
        if deterministic is not None:
            return deterministic

        atr = None
        try:
            df_daily = self.provider.get_bars(symbol, interval="1d")
            df_4h = self.provider.get_bars(symbol, interval="4h")
            mtf = build_trade_pipeline().compute_from_cache(symbol, df_daily=df_daily, df_4h=df_4h)
            atr = mtf.daily.atr if mtf and mtf.daily else None
        except Exception as exc:
            logger.warning("Could not fetch ATR for review of %s: %s", symbol, exc)

        current_price = float(position.current_price or 0.0)
        unrealized_pnl_pct = float(position.unrealized_plpc or 0.0)
        original_thesis = self._original_thesis(symbol, meta)

        logger.info(
            "Reviewing %s | Price: %s | PnL: %.2f%%",
            symbol,
            current_price,
            unrealized_pnl_pct * 100,
        )

        decision = self.portfolio_agent.review_position(
            symbol=symbol,
            current_price=current_price,
            unrealized_pnl_pct=unrealized_pnl_pct,
            atr=atr,
            original_thesis=original_thesis,
        )

        return self._normalize_decision(decision)

    def _deterministic_review(
        self,
        position,
        meta: PositionMeta | None,
    ) -> PortfolioDecision | None:
        if meta is None or meta.created_at is None:
            return None

        opened_at = meta.created_at
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)
        holding_days = (datetime.now(timezone.utc) - opened_at).days
        max_horizon = meta.expected_horizon_days or self.policy.max_hold_days

        if holding_days > max_horizon:
            return PortfolioDecision(
                action="EXIT",
                reasoning=[f"Max holding horizon exceeded ({holding_days}d > {max_horizon}d)."],
            )

        if holding_days < self.policy.min_hold_days:
            return PortfolioDecision(
                action="HOLD",
                reasoning=[f"Minimum holding period still active ({holding_days}d)."],
            )

        return None

    def _position_meta(self, symbol: str) -> PositionMeta | None:
        return self.pos_repo.get_by_symbol(symbol)

    def _original_thesis(
        self,
        symbol: str,
        meta: PositionMeta | None,
    ) -> list[str]:
        thesis: list[str] = []
        if meta and meta.thesis:
            thesis.append(f"Thesis: {meta.thesis}")
        if meta and meta.invalidation:
            thesis.append(f"Invalidation: {meta.invalidation}")

        last_decision = self.trade_repo.get_last_buy_decision(symbol)
        if last_decision:
            thesis.extend(last_decision.reasoning)

        return thesis

    def _normalize_decision(self, decision: PortfolioDecision) -> PortfolioDecision:
        action = decision.action.upper()
        if action == "CLOSE_EARLY":
            action = "EXIT"
        if action not in _ALLOWED_ACTIONS:
            return PortfolioDecision(
                action="HOLD",
                reasoning=[*decision.reasoning, f"Rejected unsupported review action: {action}."],
            )

        return PortfolioDecision(action=action, reasoning=decision.reasoning)

    def _is_accepted(self, decision: PortfolioDecision) -> tuple[bool, str | None]:
        if decision.action not in _ALLOWED_ACTIONS:
            return False, "review attempted an unsupported action"
        return True, None

    def _record_review(
        self,
        symbol: str,
        decision: PortfolioDecision,
        accepted: bool,
        rejection_reason: str | None,
    ) -> None:
        self.pos_repo.add_review_record(
            symbol=symbol,
            action=decision.action,
            accepted=accepted,
            rejection_reason=rejection_reason,
            reasoning=decision.reasoning,
            data={"source": "position_review"},
        )
