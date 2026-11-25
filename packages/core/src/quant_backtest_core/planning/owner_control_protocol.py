"""Fixed synthetic panels, separate from policy parameters and financial ownership."""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict

from .owner_control_case import OwnerControlCase

POLICIES = ("immediate", "open_loop", "twap", "rolling")


def case_id(case: OwnerControlCase) -> str:
    return hashlib.sha256(
        json.dumps(asdict(case), sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def fixed_panels() -> list[tuple[str, OwnerControlCase]]:
    rows = []
    for belief, actual, policy in itertools.product((0.5, 1.0, 2.0), (0.5, 1.0, 2.0), POLICIES):
        rows.append(
            (
                "impact",
                OwnerControlCase(policy=policy, belief_multiplier=belief, actual_multiplier=actual),
            )
        )
    for quantity, participation, policy in itertools.product(
        (80, 400, 1200), (0.05, 0.1, 0.2), POLICIES
    ):
        rows.append(
            (
                "capacity",
                OwnerControlCase(policy=policy, quantity=quantity, participation=participation),
            )
        )
    for delay, latency, liquidity, policy in itertools.product(
        (0.0, 300.0), (0, 1), ("normal", "outage"), POLICIES
    ):
        rows.append(
            (
                "feedback",
                OwnerControlCase(
                    policy=policy,
                    report_delay_seconds=delay,
                    latency_minutes=latency,
                    liquidity=liquidity,
                ),
            )
        )
    return rows
