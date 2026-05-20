from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agentic_trader.broker.mapper import to_broker_fill
from agentic_trader.broker.models import BrokerFill
from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.database.models import Decision, OrderIntent, Trade
from agentic_trader.database.repositories.trades import TradeRepository

logger = logging.getLogger(__name__)


class AggregatedFill(BaseModel):
    order_id: str
    client_order_id: str | None = None
    symbol: str
    side: str
    qty: float
    price: float
    transaction_time: datetime | None = None


class PnLSyncSummary(BaseModel):
    fills_seen: int = 0
    trades_upserted: int = 0
    trades_closed: int = 0
    reconciliation_issues: list[str] = Field(default_factory=list)


class FillPnLSync:
    """Synchronize local trade PnL from broker-confirmed fills."""

    def __init__(self, session: Session, alpaca: AlpacaController):
        self.session = session
        self.alpaca = alpaca
        self.trades = TradeRepository(session)

    def run(self) -> PnLSyncSummary:
        fills = self._fetch_fills()
        summary = PnLSyncSummary(fills_seen=len(fills))

        for fill in self._aggregate_fills(fills):
            trade = self._upsert_trade_from_fill(fill)
            summary.trades_upserted += 1
            if fill.side == "sell" and trade.closed_at is None:
                closed_count = self._apply_sell_fill(trade, fill)
                summary.trades_closed += closed_count
                if trade.needs_reconciliation and trade.reconciliation_reason:
                    summary.reconciliation_issues.append(trade.reconciliation_reason)

        self.session.commit()
        logger.info(
            "Fill PnL sync complete: fills=%d upserted=%d closed=%d issues=%d",
            summary.fills_seen,
            summary.trades_upserted,
            summary.trades_closed,
            len(summary.reconciliation_issues),
        )

        return summary

    def _fetch_fills(self) -> list[BrokerFill]:
        activities = self.alpaca.get_fill_activities(page_size=100)
        fills: list[BrokerFill] = []
        for activity in activities:
            try:
                fills.append(to_broker_fill(activity))
            except Exception as exc:
                logger.warning("Skipping malformed fill activity: %s", exc)

        return fills

    def _aggregate_fills(self, fills: list[BrokerFill]) -> list[AggregatedFill]:
        by_order: dict[tuple[str, str, str], list[BrokerFill]] = {}
        for fill in fills:
            if not fill.order_id or fill.qty <= 0 or fill.price <= 0 or not fill.side:
                continue
            key = (fill.order_id, fill.symbol.upper(), fill.side.lower())
            by_order.setdefault(key, []).append(fill)

        aggregated: list[AggregatedFill] = []
        for (order_id, symbol, side), order_fills in by_order.items():
            qty = sum(fill.qty for fill in order_fills)
            notional = sum(fill.qty * fill.price for fill in order_fills)
            transaction_time = max(
                (fill.transaction_time for fill in order_fills if fill.transaction_time),
                default=None,
            )
            client_order_id = next(
                (fill.client_order_id for fill in order_fills if fill.client_order_id),
                None,
            )
            aggregated.append(
                AggregatedFill(
                    order_id=order_id,
                    client_order_id=client_order_id,
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    price=notional / qty,
                    transaction_time=transaction_time,
                )
            )

        return sorted(aggregated, key=_fill_sort_key)

    def _upsert_trade_from_fill(self, fill: AggregatedFill) -> Trade:
        intent = self._intent_for_fill(fill)
        decision_id = self._decision_id_for_intent(intent)
        trade = self.session.query(Trade).filter_by(alpaca_order_id=fill.order_id).first()
        was_processed_sell = trade is not None and trade.side == "sell" and trade.closed_at is not None
        if trade is None:
            trade = Trade(
                symbol=fill.symbol,
                side=fill.side,
                qty=fill.qty,
                price=fill.price,
                alpaca_order_id=fill.order_id,
                timestamp=fill.transaction_time or datetime.now(timezone.utc),
                decision_id=decision_id,
            )
            self.session.add(trade)
        else:
            trade.symbol = fill.symbol
            trade.side = fill.side
            trade.qty = fill.qty
            trade.price = fill.price
            if fill.transaction_time is not None:
                trade.timestamp = fill.transaction_time
            if trade.decision_id is None:
                trade.decision_id = decision_id

        if not was_processed_sell:
            trade.needs_reconciliation = False
            trade.reconciliation_reason = None
        if decision_id is not None:
            self._mark_decision_executed(decision_id)
            if fill.side == "buy":
                self._update_position_meta(fill.symbol, decision_id)
        return trade

    def _update_position_meta(self, symbol: str, decision_id: int) -> None:
        decision = self.session.query(Decision).filter_by(id=decision_id).first()
        if not decision:
            return

        from agentic_trader.database.models import PositionMeta

        meta = self.session.query(PositionMeta).filter_by(symbol=symbol.upper()).first()
        if not meta:
            meta = PositionMeta(symbol=symbol.upper())
            self.session.add(meta)

        meta.decision_id = decision_id
        meta.thesis = decision.thesis
        meta.invalidation = decision.invalidation
        meta.expected_horizon_days = decision.expected_horizon_days

    def _apply_sell_fill(self, sell_trade: Trade, fill: AggregatedFill) -> int:
        sell_trade.closed_at = fill.transaction_time or datetime.now(timezone.utc)
        sell_trade.close_price = fill.price
        remaining_qty = fill.qty
        closed_count = 0
        open_buys = (
            self.session.query(Trade)
            .filter(Trade.symbol == fill.symbol)
            .filter(Trade.side == "buy")
            .filter(Trade.closed_at.is_(None))
            .filter(Trade.price.isnot(None))
            .order_by(Trade.timestamp.asc())
            .all()
        )

        for buy_trade in open_buys:
            if remaining_qty <= 0:
                break
            if buy_trade.qty > remaining_qty + 1e-9:
                self._mark_reconciliation_issue(
                    sell_trade,
                    f"Partial close for {fill.symbol} requires lot splitting",
                )
                break

            self.trades.close_trade(buy_trade, fill.price, closed_at=fill.transaction_time)
            remaining_qty -= buy_trade.qty
            closed_count += 1

        if remaining_qty > 1e-9:
            self._mark_reconciliation_issue(
                sell_trade,
                f"Sell fill for {fill.symbol} has {remaining_qty:.8f} unmatched shares",
            )

        return closed_count

    def _mark_reconciliation_issue(self, trade: Trade, reason: str) -> None:
        trade.needs_reconciliation = True
        trade.reconciliation_reason = reason
        logger.warning("Trade %s needs reconciliation: %s", trade.id, reason)

    def _intent_for_fill(self, fill: AggregatedFill) -> OrderIntent | None:
        intent = self.session.query(OrderIntent).filter_by(broker_order_id=fill.order_id).first()
        if intent is not None or fill.client_order_id is None:
            return intent

        return self.session.query(OrderIntent).filter_by(client_order_id=fill.client_order_id).first()

    def _decision_id_for_intent(self, intent: OrderIntent | None) -> int | None:
        if intent is None or not intent.data:
            return None

        raw_decision_id = intent.data.get("decision_id")
        if raw_decision_id is None:
            return None

        try:
            return int(raw_decision_id)
        except (TypeError, ValueError):
            return None

    def _mark_decision_executed(self, decision_id: int) -> None:
        decision = self.session.query(Decision).filter_by(id=decision_id).first()
        if decision is not None:
            decision.executed = True


def _fill_sort_key(fill: AggregatedFill) -> tuple[datetime, str]:
    timestamp = fill.transaction_time or datetime.min.replace(tzinfo=timezone.utc)
    return timestamp, fill.order_id
