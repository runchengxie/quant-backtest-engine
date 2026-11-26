"""Independent bounded synthetic price-path and terminal-capacity experiments."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from quant_backtest_core.backtest.impact import LinearImpact
from quant_backtest_core.backtest.minute_session import MinuteSession

from . import owner_control, owner_control_case
from .owner_control import OwnerLiquidationPolicy
from .owner_control_case import OwnerControlCase, case_inputs


@dataclass(frozen=True)
class StudyCase:
    base: OwnerControlCase
    price_path: str = "flat"
    reserve_slots: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.base, OwnerControlCase):
            raise ValueError("OwnerControlCase base required")
        if self.price_path not in ("flat", "up", "down", "oscillating", "jump"):
            raise ValueError("unsupported price path")
        if type(self.reserve_slots) is not int or self.reserve_slots not in (0, 1):
            raise ValueError("reserve_slots must be 0 or 1")
        if self.reserve_slots and self.base.policy != "rolling":
            raise ValueError("reserve requires rolling policy")


def fingerprints() -> dict[str, Any]:
    value = owner_control.fingerprints()
    value["sources"].update(
        {
            module.__name__: hashlib.sha256(Path(str(module.__file__)).read_bytes()).hexdigest()
            for module in (owner_control, owner_control_case)
        }
    )
    return value


class StudyLiquidationPolicy(OwnerLiquidationPolicy):
    """Inherited delivered-state decisions with a smaller planning horizon."""

    def __init__(self, case: StudyCase) -> None:
        super().__init__(case.base)
        self.reserve_slots = case.reserve_slots
        self.case_binding = hashlib.sha256(
            json.dumps(asdict(case), sort_keys=True, allow_nan=False).encode()
        ).hexdigest()

    def _plan(self, quantity: int, slots: int) -> Any:
        return super()._plan(quantity, max(1, slots - self.reserve_slots))

    def checkpoint(self) -> dict[str, Any]:
        value = super().checkpoint()
        value.update(schema="study-liquidation-policy.v1", dependencies=fingerprints())
        value["control"]["reserve_slots"] = self.reserve_slots
        return value

    def _validate_state(self, checkpoint: dict[str, Any]) -> None:
        super()._validate_state(checkpoint)
        replay = copy.copy(self)
        replay.trace = []
        replay.fixed_sales = replay.fixed_continuous = replay.fixed_failure = None
        for row in checkpoint["trace"]:
            if row["slot"] == -1:
                if (
                    set(row) != {"time", "slot", "policy", "action", "target_quantity"}
                    or type(row["target_quantity"]) is not int
                ):
                    raise ValueError("invalid policy bootstrap keys")
                replay(SimpleNamespace(time=pd.Timestamp(row["time"])), {})
                continue
            keys = {
                "time",
                "slot",
                "policy",
                "action",
                "delivered_quantity",
                "pending_count",
                "remaining_slots",
                "continuous_sales",
                "integer_sales",
                "target_quantity",
                "target_weight",
                "failure",
            }
            if set(row) != keys:
                raise ValueError("invalid policy decision keys")
            action = row["action"]
            if type(row["remaining_slots"]) is not int:
                raise ValueError("invalid policy remaining slots")
            if row["delivered_quantity"] > self.control.quantity:
                raise ValueError("invalid policy holdings")
            if row["pending_count"] and action != "wait_pending":
                raise ValueError("invalid policy pending gate")
            if action == "wait_pending" and not row["pending_count"]:
                raise ValueError("invalid policy pending action")
            if action == "empty" and row["delivered_quantity"]:
                raise ValueError("invalid policy empty action")
            if action == "submit":
                sales, continuous = row["integer_sales"], row["continuous_sales"]
                if (
                    not sales
                    or len(sales) != len(continuous)
                    or any(type(q) is not int or q < 0 for q in sales)
                    or any(
                        type(q) not in (int, float) or not math.isfinite(q) or q < 0
                        for q in continuous
                    )
                    or type(row["target_quantity"]) is not int
                    or row["target_quantity"] != max(0, row["delivered_quantity"] - sales[0])
                    or type(row["target_weight"]) not in (int, float)
                    or not math.isfinite(row["target_weight"])
                    or row["target_weight"] < 0
                    or (row["target_quantity"] == 0) != (row["target_weight"] == 0)
                    or row["failure"] is not None
                ):
                    raise ValueError("invalid policy submission")
            elif (
                row["integer_sales"]
                or row["continuous_sales"]
                or row["target_quantity"] is not None
                or row["target_weight"] is not None
            ):
                raise ValueError("invalid policy inactive fields")
            if action == "planning_failure":
                if not isinstance(row["failure"], str) or not row["failure"].strip():
                    raise ValueError("invalid policy failure")
            elif row["failure"] is not None:
                raise ValueError("invalid policy failure field")
            replay(
                SimpleNamespace(
                    time=pd.Timestamp(row["time"]),
                    holdings={"A": row["delivered_quantity"]},
                    pending_orders=[None] * row["pending_count"],
                    marks={"A": 1.0},
                    nav=1.0,
                ),
                {},
            )
            expected_row = dict(replay.trace[-1])
            actual_row = dict(row)
            expected_row.pop("target_weight")
            actual_row.pop("target_weight")
            if actual_row != expected_row:
                raise ValueError("invalid policy decision replay")
        for field in ("fixed_sales", "fixed_continuous", "fixed_failure"):
            if checkpoint[field] != getattr(replay, field):
                raise ValueError("invalid policy schedule replay")

    @classmethod
    def restore(cls, case: StudyCase, checkpoint: Any) -> StudyLiquidationPolicy:  # type: ignore[override]
        policy = cls(case)
        expected = policy.checkpoint()
        if (
            not isinstance(checkpoint, dict)
            or set(checkpoint) != set(expected)
            or any(
                checkpoint.get(key) != expected[key]
                for key in ("schema", "control", "case_binding", "dependencies")
            )
        ):
            raise ValueError("policy schema/configuration/dependency binding mismatch")
        try:
            if json.dumps(checkpoint["control"], sort_keys=True, allow_nan=False) != json.dumps(
                expected["control"], sort_keys=True, allow_nan=False
            ):
                raise ValueError("invalid policy control types")
            policy._validate_state(checkpoint)
            json.dumps(checkpoint, allow_nan=False)
            for name in ("trace", "fixed_sales", "fixed_continuous", "fixed_failure"):
                setattr(policy, name, copy.deepcopy(checkpoint[name]))
        except (TypeError, KeyError, ValueError, OverflowError) as exc:
            raise ValueError("invalid policy checkpoint") from exc
        return policy


def study_inputs(case: StudyCase) -> tuple[Any, Any, Any]:
    targets, bars, config = case_inputs(case.base)
    paths = {
        "flat": [10.0] * 8,
        "up": [10 + 0.02 * i for i in range(8)],
        "down": [10 - 0.02 * i for i in range(8)],
        "oscillating": [10 + x for x in (0, 0.04, -0.04, 0.04, -0.04, 0.04, -0.04, 0)],
        "jump": [10.0] * 6 + [9.8] * 2,
    }
    prices = [10.0] * 3 + [p for p in paths[case.price_path] for _ in range(3)]
    prices += [prices[-1]] * (len(bars) - len(prices))
    for field in ("open", "high", "low", "close"):
        bars[field] = prices
    bars["amount"] = bars.close * bars.volume
    return targets, bars, config


def build_study(case: StudyCase, *, bars: pd.DataFrame | None = None) -> MinuteSession:
    targets, fixture, config = study_inputs(case)
    return MinuteSession(
        targets,
        fixture if bars is None else bars,
        config,
        policy=StudyLiquidationPolicy(case),
        report_delay_seconds=case.base.report_delay_seconds,
        impact=LinearImpact(
            transient=1e-4 * case.base.actual_multiplier, permanent=0, decay_seconds=300
        ),
    )


def restore_study(
    case: StudyCase, checkpoint: dict[str, Any], *, bars: pd.DataFrame | None = None
) -> MinuteSession:
    policy = StudyLiquidationPolicy.restore(case, checkpoint.get("policy"))
    targets, fixture, config = study_inputs(case)
    if checkpoint.get("delay") != case.base.report_delay_seconds:
        raise ValueError("case report delay binding mismatch")
    return MinuteSession.restore(
        targets, fixture if bars is None else bars, config, checkpoint, policy=policy
    )


def run_study(case: StudyCase) -> tuple[Any, dict[str, Any]]:
    session = build_study(case)
    while session.step():
        pass
    checkpoint = session.checkpoint()
    return session.run(), {
        "policy_trace": session.policy.checkpoint()["trace"],
        "delivery_trace": list(session.trace),
        "checkpoint": checkpoint,
    }
