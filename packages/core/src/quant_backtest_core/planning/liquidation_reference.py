"""Continuous LQ liquidation benchmark; no execution, cash ledger or calibration.

Units: x shares, t seconds, eta currency*seconds/shares², sigma
currency/(share*sqrt(second)), risk_aversion 1/currency. The objective is
integral(eta*v² + risk_aversion*sigma²*x²) dt in currency, with x(T)=0.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class LiquidationModel:
    initial_inventory: float
    horizon_seconds: float
    temporary_cost: float
    risk_aversion: float
    volatility: float


@dataclass(frozen=True)
class LiquidationPoint:
    inventory: float
    sell_rate: float
    remaining_value: float


def evaluate(model: LiquidationModel, elapsed_seconds: float) -> LiquidationPoint:
    """Evaluate the optimal path from the initial state, not a realized fill.

    The terminal rate is its left limit. Remaining value is zero at the reached
    terminal state; this does not assign finite value to nonzero terminal stock.
    Reject unrepresentable coefficient/time/cost domains rather than certify them.
    """
    values = (
        model.initial_inventory,
        model.horizon_seconds,
        model.temporary_cost,
        model.risk_aversion,
        model.volatility,
        elapsed_seconds,
    )
    if not all(math.isfinite(v) for v in values):
        raise ValueError("finite coefficients and elapsed seconds required")
    x, horizon, eta, risk, sigma, elapsed = values
    if x < 0 or horizon <= 0 or eta <= 0 or risk < 0 or sigma < 0:
        raise ValueError("nonnegative inventory/risk/volatility and positive horizon/eta required")
    if not 0 <= elapsed <= horizon:
        raise ValueError("elapsed seconds must lie in the closed horizon")
    risk_scale = math.sqrt(risk) * sigma
    if risk > 0 and sigma > 0 and risk_scale < sys.float_info.min:
        raise ValueError("positive risk coefficient underflows the supported domain")
    kappa = risk_scale / math.sqrt(eta)
    z = kappa * horizon
    if not math.isfinite(kappa) or not math.isfinite(z):
        raise ValueError("coefficient/time domain is unrepresentable")
    if x > 0 and eta * x < sys.float_info.min:
        raise ValueError("initial cost scale underflows the supported domain")
    # Validate the full initial objective even when querying a terminal/zero path.
    if z < 1e-8:
        rate = x / horizon
        if x > 0 and rate < sys.float_info.min:
            raise ValueError("initial rate underflows the supported domain")
        inventory = x * ((horizon - elapsed) / horizon)
        initial_value = eta * x * rate
    else:
        if x > 0 and x * kappa < sys.float_info.min:
            raise ValueError("initial rate scale underflows the supported domain")
        denominator = -math.expm1(-2 * z)
        decay = math.exp(-kappa * elapsed)
        tail = kappa * (horizon - elapsed)
        inventory = x * decay * (-math.expm1(-2 * tail) / denominator)
        rate = (x * kappa) * decay * ((1 + math.exp(-2 * tail)) / denominator)
        initial_value = (eta * x) * (x * kappa) * ((1 + math.exp(-2 * z)) / denominator)
    if x > 0 and initial_value == 0:
        raise ValueError("initial objective underflows the supported domain")
    value = (eta * inventory) * rate
    if not all(math.isfinite(v) for v in (inventory, rate, value, initial_value)):
        raise ValueError("inventory/rate/value domain is unrepresentable")
    # Floating-point underflow in late liquidation tails is rounded to zero.
    return LiquidationPoint(x if elapsed == 0 else inventory, rate, value)
