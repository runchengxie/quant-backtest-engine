"""Deterministic synthetic owner-control fixtures; no production policy defaults."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from quant_backtest_core.backtest.impact import LinearImpact
from quant_backtest_core.backtest.minute import MinuteExecutionConfig
from quant_backtest_core.backtest.minute_session import MinuteSession

from .owner_control import OwnerLiquidationPolicy


@dataclass(frozen=True)
class OwnerControlCase:
    policy: str = "rolling"
    quantity: int = 400
    participation: float = 0.1
    belief_multiplier: float = 1.0
    actual_multiplier: float = 1.0
    report_delay_seconds: float = 0.0
    latency_minutes: int = 0
    liquidity: str = "normal"

    def __post_init__(self) -> None:
        if self.policy not in ("immediate", "open_loop", "twap", "rolling"):
            raise ValueError("unsupported policy")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("positive integer quantity required")
        if type(self.latency_minutes) is not int or self.latency_minutes not in (0, 1):
            raise ValueError("latency must be 0 or 1 minute")
        for name in (
            "participation",
            "belief_multiplier",
            "actual_multiplier",
            "report_delay_seconds",
        ):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v < 0:
                raise ValueError(f"finite nonnegative scalar {name} required")
        if not 0 < self.participation <= 1 or self.belief_multiplier <= 0:
            raise ValueError("positive participation <= 1 and belief required")
        if self.liquidity not in ("normal", "outage"):
            raise ValueError("unsupported liquidity")


def case_inputs(case: OwnerControlCase) -> tuple[pd.DataFrame, pd.DataFrame, MinuteExecutionConfig]:
    """Return fresh targets/bars/config; actual future bars never enter policy."""
    seed = pd.Timestamp("2025-01-02 09:30", tz="Asia/Shanghai")
    start = pd.Timestamp("2025-01-03 09:30", tz="Asia/Shanghai")
    entries = [seed] + [start + pd.Timedelta(minutes=4 * i) for i in range(8)]
    targets = pd.DataFrame(
        [
            {
                "decision_time": t - pd.Timedelta(minutes=1),
                "entry_time": t,
                "symbol": "A",
                "weight": 0.5 if i == 0 else 0.0,
            }
            for i, t in enumerate(entries)
        ]
    )
    rows = []
    for i, entry in enumerate(entries):
        for delta in (-1.5, 1, 2):
            time = entry + pd.Timedelta(minutes=delta)
            volume = 1e6 if i == 0 else (0 if case.liquidity == "outage" and i in (1, 2) else 500)
            rows.append(
                {
                    "time": time,
                    "interval_start": time - pd.Timedelta(seconds=30),
                    "symbol": "A",
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": volume,
                    "amount": 10 * volume,
                    "up_limit": 15.0,
                    "down_limit": 5.0,
                    "tradable": True,
                }
            )
    # Mark-only reports drain; order deadline remains entry+2 minutes.
    last = entries[-1] + pd.Timedelta(minutes=2)
    for minute in range(1, 13):
        row = dict(rows[-1])
        row.update(time=last + pd.Timedelta(minutes=minute), volume=0.0, amount=0.0)
        row["interval_start"] = row["time"] - pd.Timedelta(seconds=30)
        rows.append(row)
    config = MinuteExecutionConfig(
        20 * case.quantity,
        case.participation,
        3,
        8,
        lot_size=1,
        execution_minutes=2,
        latency_minutes=case.latency_minutes,
        commission_minimum_cny=0,
        sell_tax_bp=5,
    )
    return targets, pd.DataFrame(rows), config


def build_session(case: OwnerControlCase, *, bars: pd.DataFrame | None = None) -> MinuteSession:
    targets, fixture, config = case_inputs(case)
    return MinuteSession(
        targets,
        fixture if bars is None else bars,
        config,
        policy=OwnerLiquidationPolicy(case),
        report_delay_seconds=case.report_delay_seconds,
        impact=LinearImpact(
            transient=1e-4 * case.actual_multiplier, permanent=0, decay_seconds=300
        ),
    )


def restore_case(
    case: OwnerControlCase, checkpoint: dict[str, Any], *, bars: pd.DataFrame | None = None
) -> MinuteSession:
    policy = OwnerLiquidationPolicy.restore(case, checkpoint.get("policy"))
    targets, fixture, config = case_inputs(case)
    if checkpoint.get("delay") != case.report_delay_seconds:
        raise ValueError("case report delay binding mismatch")
    return MinuteSession.restore(
        targets, fixture if bars is None else bars, config, checkpoint, policy=policy
    )


def run_case(case: OwnerControlCase) -> tuple[Any, dict[str, Any]]:
    session = build_session(case)
    while session.step():
        pass
    checkpoint = session.checkpoint()
    result = session.run()
    return result, {
        "policy_trace": session.policy.checkpoint()["trace"],
        "delivery_trace": list(session.trace),
        "checkpoint": checkpoint,
    }
