# Extracted from quant-platform/packages/platform/src/quant_platform/backtest/impact_scenarios.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Uncalibrated linear impact sensitivity model, separate from historical replay.

Prices are currency/share; signed quantities are shares; permanent and temporary
coefficients are currency/share**2. Midpoint integration prevents mechanical
round-trip profit for linear permanent impact. No historical prices are changed.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, isfinite


@dataclass(frozen=True)
class ImpactFill:
    quantity: float
    execution_price: float
    fee: float


@dataclass(frozen=True)
class ImpactScenario:
    fills: tuple[ImpactFill, ...]
    cash_change: float
    final_inventory: float
    final_displacement: float


def linear_impact_scenario(
    quantities: Sequence[float],
    *,
    unaffected_price: float,
    permanent: float = 0,
    temporary: float = 0,
    fee_per_share: float = 0,
) -> ImpactScenario:
    """Execute a synthetic path at a fixed unaffected price, starting flat.

    Execution = unaffected price + prior displacement + permanent*q/2 +
    temporary*q. Fees are separate currency amounts and charged exactly once.
    Temporary cost is quadratic in each slice and has no time/volume calibration.
    Negative modeled execution prices are rejected, not clipped.
    """
    parameters = (unaffected_price, permanent, temporary, fee_per_share)
    if any(isinstance(v, bool) or not isfinite(v) for v in parameters):
        raise ValueError("parameters must be finite numbers")
    if unaffected_price <= 0 or min(permanent, temporary, fee_per_share) < 0:
        raise ValueError("price must be positive and coefficients nonnegative")
    values = tuple(quantities)
    if any(isinstance(q, bool) or not isfinite(q) for q in values):
        raise ValueError("quantities must be finite numbers")
    inventory = 0.0
    fills = []
    for q in values:
        price = unaffected_price + permanent * inventory + permanent * q / 2 + temporary * q
        if not isfinite(price) or price <= 0:
            raise ValueError("modeled execution price must be finite and positive")
        fills.append(ImpactFill(q, price, fee_per_share * abs(q)))
        inventory = fsum((inventory, q))
    cash = -fsum(f.quantity * f.execution_price + f.fee for f in fills)
    displacement = permanent * inventory
    if not all(isfinite(v) for v in (cash, inventory, displacement)):
        raise ValueError("scenario overflow")
    return ImpactScenario(tuple(fills), cash, inventory, displacement)
