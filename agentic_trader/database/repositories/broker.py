from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from agentic_trader.broker.models import BrokerOrder, BrokerPosition, BrokerSnapshot
from agentic_trader.database.models import BrokerSnapshotRecord, OrderLifecycle, PositionLifecycle

logger = logging.getLogger(__name__)


class BrokerRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_snapshot(self, snapshot: BrokerSnapshot) -> BrokerSnapshotRecord:
        record = BrokerSnapshotRecord(
            fetched_at=snapshot.fetched_at,
            account_id=snapshot.account.account_id,
            status=snapshot.account.status,
            currency=snapshot.account.currency,
            cash=snapshot.account.cash,
            buying_power=snapshot.account.buying_power,
            equity=snapshot.account.equity,
            portfolio_value=snapshot.account.portfolio_value,
            invested_value=snapshot.invested_value,
            position_count=len(snapshot.positions),
            open_order_count=len(snapshot.open_orders),
            issue_count=len(snapshot.issues),
            data=snapshot.model_dump(mode="json"),
        )
        self.session.add(record)
        self.session.flush()

        orders_by_id = {
            order.order_id: order
            for order in [*snapshot.open_orders, *snapshot.recent_orders]
            if order.order_id
        }
        for order in orders_by_id.values():
            self.upsert_order_lifecycle(order, seen_at=snapshot.fetched_at)

        self.sync_position_lifecycles(snapshot.positions, seen_at=snapshot.fetched_at)

        logger.info(
            "Broker snapshot persisted: id=%s positions=%d open_orders=%d",
            record.id,
            len(snapshot.positions),
            len(snapshot.open_orders),
        )

        return record

    def latest_snapshot(self) -> BrokerSnapshotRecord | None:
        return (
            self.session.query(BrokerSnapshotRecord).order_by(BrokerSnapshotRecord.fetched_at.desc()).first()
        )

    def list_order_lifecycles(self, symbol: str | None = None, limit: int = 100) -> list[OrderLifecycle]:
        query = self.session.query(OrderLifecycle).order_by(OrderLifecycle.last_seen_at.desc())
        if symbol:
            query = query.filter(OrderLifecycle.symbol == symbol.upper())
        return list(query.limit(limit).all())

    def list_position_lifecycles(self, status: str | None = None) -> list[PositionLifecycle]:
        query = self.session.query(PositionLifecycle).order_by(PositionLifecycle.last_broker_seen_at.desc())
        if status:
            query = query.filter(PositionLifecycle.status == status)
        return list(query.all())

    def upsert_order_lifecycle(self, order: BrokerOrder, *, seen_at: datetime) -> OrderLifecycle:
        lifecycle = (
            self.session.query(OrderLifecycle)
            .filter(OrderLifecycle.broker_order_id == order.order_id)
            .first()
        )
        if lifecycle is None:
            lifecycle = OrderLifecycle(broker_order_id=order.order_id)
            self.session.add(lifecycle)

        lifecycle.client_order_id = order.client_order_id
        lifecycle.symbol = order.symbol
        lifecycle.side = order.side
        lifecycle.order_type = order.order_type
        lifecycle.order_class = order.order_class
        lifecycle.status = order.status
        lifecycle.qty = order.qty
        lifecycle.filled_qty = order.filled_qty
        lifecycle.filled_avg_price = order.filled_avg_price
        lifecycle.limit_price = order.limit_price
        lifecycle.stop_price = order.stop_price
        lifecycle.submitted_at = order.submitted_at
        lifecycle.broker_updated_at = order.updated_at
        lifecycle.last_seen_at = seen_at
        lifecycle.data = order.model_dump(mode="json")

        return lifecycle

    def sync_position_lifecycles(
        self,
        positions: list[BrokerPosition],
        *,
        seen_at: datetime,
    ) -> None:
        seen_symbols = {position.symbol for position in positions}
        for position in positions:
            lifecycle = (
                self.session.query(PositionLifecycle)
                .filter(PositionLifecycle.symbol == position.symbol)
                .first()
            )
            if lifecycle is None:
                lifecycle = PositionLifecycle(symbol=position.symbol, opened_at=seen_at)
                self.session.add(lifecycle)

            lifecycle.status = "open"
            lifecycle.closed_at = None
            lifecycle.qty = position.qty
            lifecycle.avg_entry_price = position.avg_entry_price
            lifecycle.market_value = position.market_value
            lifecycle.current_price = position.current_price
            lifecycle.unrealized_pl = position.unrealized_pl
            lifecycle.unrealized_plpc = position.unrealized_plpc
            lifecycle.last_broker_seen_at = seen_at
            lifecycle.data = position.model_dump(mode="json")

        stale_positions = (
            self.session.query(PositionLifecycle)
            .filter(PositionLifecycle.status == "open")
            .filter(~PositionLifecycle.symbol.in_(seen_symbols))
            .all()
        )
        for lifecycle in stale_positions:
            lifecycle.status = "missing_from_broker"
            lifecycle.last_broker_seen_at = seen_at
