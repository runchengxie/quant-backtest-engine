# SPDX-License-Identifier: Apache-2.0
# Source: quant-research b926125dd1edb9055da28aec8c8de1800fc066f0,
# src/strategy_research/l2_50m_projection.py
"""Finite historical participation and one-snapshot depth diagnostics."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Any, Self

import numpy as np


@dataclass
class TradeTape:
    quantities: np.ndarray[Any, Any]
    prices: np.ndarray[Any, Any]
    cumulative_volume: np.ndarray[Any, Any]
    cumulative_notional: np.ndarray[Any, Any]

    @classmethod
    def build(cls, quantities: Sequence[int], prices: Sequence[int]) -> Self:
        quantity_array = np.asarray(quantities, dtype=np.int64)
        price_array = np.asarray(prices, dtype=np.int64)
        if (
            len(quantity_array) != len(price_array)
            or np.any(quantity_array <= 0)
            or np.any(price_array <= 0)
        ):
            raise ValueError("trade quantities/prices must be positive integer arrays")
        volume = sum(map(int, quantity_array))
        if volume > np.iinfo(np.int64).max:
            raise ValueError("volume exceeds supported exact cumulative range")
        safe = not len(price_array) or int(price_array.max()) * volume <= np.iinfo(np.int64).max
        raw_amount = (
            quantity_array * price_array if safe else quantity_array.astype(object) * price_array
        )
        return cls(
            quantity_array,
            price_array,
            np.r_[0, np.cumsum(quantity_array)],
            np.r_[0, np.cumsum(raw_amount)],
        )

    def project(
        self, start: int, end: int, demand: Decimal, rate: Decimal, divisor: Decimal
    ) -> dict[str, int | str | None]:
        if (
            not demand.is_finite()
            or demand < 0
            or not rate.is_finite()
            or not 0 < rate <= 1
            or not divisor.is_finite()
            or divisor <= 0
        ):
            raise ValueError("invalid demand, participation or price divisor")
        volume = int(self.cumulative_volume[end]) - int(self.cumulative_volume[start])
        filled = min(demand, rate * volume)
        result: dict[str, int | str | None] = {
            "observed_volume": volume,
            "projected_quantity": str(filled),
            "unfilled_quantity": str(demand - filled),
            "projected_notional_cny": "0",
            "projected_vwap_cny": None,
        }
        if filled == 0:
            return result
        required = int((filled / rate).to_integral_value(rounding=ROUND_CEILING))
        target = int(self.cumulative_volume[start]) + required
        boundary = int(np.searchsorted(self.cumulative_volume, target, side="left"))
        before_volume = int(self.cumulative_volume[boundary - 1]) - int(
            self.cumulative_volume[start]
        )
        before_amount = int(self.cumulative_notional[boundary - 1]) - int(
            self.cumulative_notional[start]
        )
        residual = filled - rate * before_volume
        notional = (rate * before_amount + residual * int(self.prices[boundary - 1])) / divisor
        result.update(
            projected_notional_cny=str(notional), projected_vwap_cny=str(notional / filled)
        )
        return result


def participation_projection(
    quantities: Sequence[int],
    prices: Sequence[int],
    demand: Decimal,
    rate: Decimal,
    *,
    price_divisor: Decimal,
) -> dict[str, int | str | None]:
    tape = TradeTape.build(quantities, prices)
    return tape.project(0, len(quantities), demand, rate, price_divisor)


def sweep_depth(levels: Iterable[tuple[Decimal, int]], demand: Decimal) -> dict[str, str | None]:
    """Consume one supplied snapshot once; never replenish it from later snapshots."""
    remaining, notional = demand, Decimal(0)
    for price, quantity in levels:
        if price <= 0 or quantity < 0:
            raise ValueError("invalid visible depth")
        filled = min(remaining, Decimal(quantity))
        remaining -= filled
        notional += filled * price
    filled = demand - remaining
    return {
        "visible_quantity": str(filled),
        "uncovered_quantity": str(remaining),
        "visible_notional_cny": str(notional),
        "visible_vwap_cny": str(notional / filled) if filled else None,
    }
