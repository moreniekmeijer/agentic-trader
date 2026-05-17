from __future__ import annotations

import os

_runtime_submissions_enabled: bool | None = None


def set_broker_submissions_enabled(enabled: bool) -> None:
    global _runtime_submissions_enabled
    _runtime_submissions_enabled = enabled


def broker_submissions_enabled() -> bool:
    if _runtime_submissions_enabled is not None:
        return _runtime_submissions_enabled

    return _env_bool("BROKER_SUBMISSIONS_ENABLED", True)


def kill_switch_enabled() -> bool:
    return not broker_submissions_enabled()


def auto_submit_order_intents_enabled() -> bool:
    return _env_bool("ORDER_INTENT_AUTO_SUBMIT", False)


def paper_trading_enabled() -> bool:
    return _env_bool("ALPACA_PAPER", True)


def broker_mode() -> str:
    return "paper" if paper_trading_enabled() else "live"


def broker_snapshot_max_age_seconds() -> int:
    raw = os.getenv("BROKER_SNAPSHOT_MAX_AGE_SECONDS")
    if raw is None:
        return 300
    try:
        return int(raw)
    except ValueError:
        return 300


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    return raw.lower() in {"1", "true", "yes", "on"}
