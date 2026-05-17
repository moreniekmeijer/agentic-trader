from __future__ import annotations

from fastapi import APIRouter

from agentic_trader.api.schemas import ExecutionControlStatus, KillSwitchRequest
from agentic_trader.execution.controls import (
    auto_submit_order_intents_enabled,
    broker_mode,
    broker_submissions_enabled,
    kill_switch_enabled,
    paper_trading_enabled,
    set_broker_submissions_enabled,
)

router = APIRouter(prefix="/control", tags=["control"])


@router.get("/status", response_model=ExecutionControlStatus)
def get_execution_control_status() -> ExecutionControlStatus:
    return _control_status()


@router.post("/kill-switch", response_model=ExecutionControlStatus)
def set_kill_switch(request: KillSwitchRequest) -> ExecutionControlStatus:
    set_broker_submissions_enabled(not request.enabled)

    return _control_status()


def _control_status() -> ExecutionControlStatus:
    return ExecutionControlStatus(
        broker_mode=broker_mode(),
        paper_trading=paper_trading_enabled(),
        broker_submissions_enabled=broker_submissions_enabled(),
        kill_switch_enabled=kill_switch_enabled(),
        order_intent_auto_submit=auto_submit_order_intents_enabled(),
    )
