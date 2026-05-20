from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from agentic_trader.broker.models import BrokerOrder, BrokerPosition, BrokerSnapshot
from agentic_trader.database.models import BrokerSnapshotRecord, OrderLifecycle

logger = logging.getLogger(__name__)

OPEN_ORDER_STATUSES = {"accepted", "held", "new", "open", "partially_filled", "pending_new"}


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

        # Removed sync_position_lifecycles since live Alpaca position is the source of truth

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

    def list_order_lifecycles(
        self,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[OrderLifecycle]:
        query = self.session.query(OrderLifecycle).order_by(OrderLifecycle.last_seen_at.desc())
        if symbol:
            query = query.filter(OrderLifecycle.symbol == symbol.upper())
        if status:
            query = query.filter(OrderLifecycle.status == status.lower())
        return list(query.limit(limit).all())

    def list_open_order_lifecycles(
        self,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[OrderLifecycle]:
        query = self.session.query(OrderLifecycle).filter(OrderLifecycle.status.in_(OPEN_ORDER_STATUSES))
        if symbol:
            query = query.filter(OrderLifecycle.symbol == symbol.upper())

        return list(query.order_by(OrderLifecycle.last_seen_at.desc()).limit(limit).all())



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


