"""Synthetic delivered-state controls; financial state remains with MinuteSession.

The LQ eta proxy matches only an isolated bucket, not transient cross-fill impact.
Whole-share plans round cumulative inventory endpoints (half up), conserving Q.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import math
import platform
from dataclasses import asdict, dataclass
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from .owner_control_case import OwnerControlCase

from . import liquidation_discrete, liquidation_reference
from .liquidation_discrete import solve
from .liquidation_reference import LiquidationModel


def fingerprints() -> dict[str, Any]:
    return {
        "sources": {
            module.__name__: hashlib.sha256(Path(str(module.__file__)).read_bytes()).hexdigest()
            for module in (liquidation_discrete, liquidation_reference)
        },
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "pandas": importlib.metadata.version("pandas"),
    }


def integer_sales(inventory: Sequence[float]) -> list[int]:
    endpoints = [max(0, math.floor(x + 0.5)) for x in inventory]
    return [a - b for a, b in zip(endpoints, endpoints[1:])]


@dataclass(frozen=True)
class ControlConfig:
    """Only prespecified control inputs cross the callback information boundary."""

    policy: str
    quantity: int
    participation: float
    belief_multiplier: float


class OwnerLiquidationPolicy:
    """Consumes only delivered account state and prespecified forecast constants."""

    def __init__(self, case: OwnerControlCase) -> None:
        self.control = ControlConfig(
            case.policy, case.quantity, case.participation, case.belief_multiplier
        )
        # The wrapper supplies the full case only for opaque recovery identity.
        self.case_binding = hashlib.sha256(
            json.dumps(asdict(case), sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        self.trace: list[dict[str, Any]] = []
        self.fixed_sales: list[int] | None = None
        self.fixed_continuous: list[float] | None = None
        self.fixed_failure: str | None = None

    def _plan(self, quantity: int, slots: int) -> liquidation_discrete.LiquidationPlan:
        model = LiquidationModel(
            quantity, slots * 240.0, 0.5e-4 * self.control.belief_multiplier * 240, 1e-4, 0.01
        )
        return solve(model, [1000 * self.control.participation] * slots)

    def __call__(self, state: Any, proposed: Any) -> dict[str, float] | None:
        if state.time.strftime("%Y-%m-%d") == "2025-01-02":
            self.trace.append(
                {
                    "time": state.time.isoformat(),
                    "slot": -1,
                    "policy": self.control.policy,
                    "action": "bootstrap",
                    "target_quantity": self.control.quantity,
                }
            )
            return proposed
        slot = (state.time.hour * 60 + state.time.minute - (9 * 60 + 29)) // 4
        holding = int(state.holdings.get("A", 0))
        row: dict[str, Any] = {
            "time": state.time.isoformat(),
            "slot": slot,
            "policy": self.control.policy,
            "delivered_quantity": holding,
            "pending_count": len(state.pending_orders),
            "remaining_slots": 8 - slot,
            "continuous_sales": [],
            "integer_sales": [],
            "target_quantity": None,
            "target_weight": None,
            "failure": None,
        }
        self.trace.append(row)
        if state.pending_orders:
            row["action"] = "wait_pending"
            return None
        if not holding:
            row["action"] = "empty"
            return None
        try:
            if self.control.policy == "immediate":
                if slot:
                    row["action"] = "fixed_consumed"
                    return None
                continuous, quantities = [float(holding)], [holding]
            elif self.control.policy in ("twap", "open_loop"):
                if self.fixed_sales is None and self.fixed_failure is None:
                    if self.control.policy == "twap":
                        inventory = [self.control.quantity * (8 - i) / 8 for i in range(9)]
                        self.fixed_continuous = [self.control.quantity / 8] * 8
                    else:
                        plan = self._plan(self.control.quantity, 8)
                        inventory, self.fixed_continuous = list(plan.inventory), list(plan.sales)
                    self.fixed_sales = integer_sales(inventory)
                if self.fixed_failure:
                    raise ValueError(self.fixed_failure)
                assert self.fixed_continuous is not None and self.fixed_sales is not None
                continuous, quantities = self.fixed_continuous[slot:], self.fixed_sales[slot:]
            else:
                plan = self._plan(holding, 8 - slot)
                continuous, quantities = list(plan.sales), integer_sales(plan.inventory)
        except ValueError as exc:
            if self.control.policy == "open_loop":
                self.fixed_failure = str(exc)
            row.update(action="planning_failure", failure=str(exc))
            return None
        desired = max(0, holding - quantities[0])
        # Midpoint of floor-sizing interval avoids floating point downward rounding.
        # Zero must be exact. No forecast cash or unseen financial state is used.
        weight = (desired + 0.5) * state.marks["A"] / state.nav if desired else 0.0
        row.update(
            action="submit",
            continuous_sales=list(continuous),
            integer_sales=list(quantities),
            target_quantity=desired,
            target_weight=weight,
        )
        return {"A": weight}

    def checkpoint(self) -> dict[str, Any]:
        value = {
            "schema": "owner-liquidation-policy.v1",
            "control": asdict(self.control),
            "case_binding": self.case_binding,
            "dependencies": fingerprints(),
            "trace": self.trace,
            "fixed_sales": self.fixed_sales,
            "fixed_continuous": self.fixed_continuous,
            "fixed_failure": self.fixed_failure,
        }
        return copy.deepcopy(value)

    def _validate_state(self, checkpoint: dict[str, Any]) -> None:
        sales, continuous = checkpoint["fixed_sales"], checkpoint["fixed_continuous"]
        failure, trace = checkpoint["fixed_failure"], checkpoint["trace"]
        if (sales is None) != (continuous is None):
            raise ValueError("invalid policy paired schedules")
        if sales is not None:
            if (
                self.control.policy not in ("twap", "open_loop")
                or not isinstance(sales, list)
                or len(sales) != 8
                or any(type(q) is not int or q < 0 for q in sales)
                or sum(sales) != self.control.quantity
                or not isinstance(continuous, list)
                or len(continuous) != 8
                or any(
                    isinstance(q, bool) or not isinstance(q, Real) or not math.isfinite(q) or q < 0
                    for q in continuous
                )
                or not math.isclose(sum(continuous), self.control.quantity, rel_tol=1e-8)
            ):
                raise ValueError("invalid policy fixed schedules")
        if failure is not None and (
            self.control.policy != "open_loop"
            or not isinstance(failure, str)
            or not failure.strip()
            or sales is not None
        ):
            raise ValueError("invalid policy fixed failure")
        if not isinstance(trace, list) or len(trace) > 9:
            raise ValueError("invalid policy trace")
        actions = {"wait_pending", "empty", "fixed_consumed", "planning_failure", "submit"}
        for index, row in enumerate(trace):
            slot = index - 1
            if (
                not isinstance(row, dict)
                or type(row.get("slot")) is not int
                or row["slot"] != slot
                or row.get("policy") != self.control.policy
                or not isinstance(row.get("time"), str)
            ):
                raise ValueError("invalid policy trace prefix")
            time = datetime.fromisoformat(row["time"])
            minute = 29 if slot == -1 else 29 + 4 * slot
            offset = time.utcoffset()
            if (
                time.strftime("%Y-%m-%d") != ("2025-01-02" if slot == -1 else "2025-01-03")
                or (time.hour, time.minute, time.second, time.microsecond) != (9, minute, 0, 0)
                or offset is None
                or offset.total_seconds() != 28800
            ):
                raise ValueError("invalid policy trace clock")
            if slot == -1:
                if (
                    row.get("action") != "bootstrap"
                    or row.get("target_quantity") != self.control.quantity
                ):
                    raise ValueError("invalid policy bootstrap trace")
                continue
            if (
                row.get("action") not in actions
                or type(row.get("delivered_quantity")) is not int
                or row["delivered_quantity"] < 0
                or type(row.get("pending_count")) is not int
                or row["pending_count"] < 0
                or row.get("remaining_slots") != 8 - slot
                or not isinstance(row.get("continuous_sales"), list)
                or not isinstance(row.get("integer_sales"), list)
            ):
                raise ValueError("invalid policy decision trace")
            if row["action"] == "fixed_consumed" and self.control.policy != "immediate":
                raise ValueError("invalid policy consumed action")
            if row["action"] == "planning_failure" and self.control.policy not in (
                "rolling",
                "open_loop",
            ):
                raise ValueError("invalid policy failure action")

    @classmethod
    def restore(cls, case: OwnerControlCase, checkpoint: Any) -> OwnerLiquidationPolicy:
        policy = cls(case)
        if (
            not isinstance(checkpoint, dict)
            or set(checkpoint) != set(policy.checkpoint())
            or checkpoint.get("schema") != "owner-liquidation-policy.v1"
            or checkpoint.get("control") != asdict(policy.control)
            or checkpoint.get("case_binding") != policy.case_binding
            or checkpoint.get("dependencies") != fingerprints()
        ):
            raise ValueError("policy schema/configuration/dependency binding mismatch")
        try:
            policy._validate_state(checkpoint)
            json.dumps(checkpoint, allow_nan=False)
            for name in ("trace", "fixed_sales", "fixed_continuous", "fixed_failure"):
                setattr(policy, name, copy.deepcopy(checkpoint[name]))
        except (TypeError, KeyError, ValueError, OverflowError) as exc:
            raise ValueError("invalid policy checkpoint") from exc
        return policy
