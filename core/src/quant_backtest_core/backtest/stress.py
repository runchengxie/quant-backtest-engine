# Extracted from quant-platform/packages/platform/src/quant_platform/backtest/stress.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Deterministic joint exogenous stress; no future-probability interpretation."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

import pandas as pd


def keyed_uniform(seed: int, symbol: str, clock: str, stream: str) -> float:
    if type(seed) is not int or any(
        not isinstance(s, str) or not s for s in (symbol, clock, stream)
    ):
        raise ValueError("integer seed and nonempty event keys required")
    payload = json.dumps(["keyed-random.v1", seed, symbol, clock, stream], separators=(",", ":"))
    bits = int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big") >> 11
    return bits / 2**53


@dataclass(frozen=True)
class JointStress:
    name: str
    seed: int = 0
    price_multiplier: float = 1.0
    volume_multiplier: float = 1.0
    risk_multiplier: float = 1.0
    impact_multiplier: float = 1.0
    liquidity_jitter: float = 0.0

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip() or type(self.seed) is not int:
            raise ValueError("scenario identity and integer seed required")
        for value in (self.price_multiplier, self.risk_multiplier, self.impact_multiplier):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("price, risk and impact multipliers must be positive")
        if not 0 <= self.volume_multiplier <= 1 or not 0 <= self.liquidity_jitter <= 1:
            raise ValueError("volume multiplier and jitter must lie in [0,1]")


def stress_bars(bars: pd.DataFrame, scenario: JointStress) -> pd.DataFrame:
    """Clip synthetic prices to fixed supplied daily limits; reduce shared capacity.

    All market rows are transformed exogenously, including pre-entry seed marks.
    Risk/impact multipliers are consumed explicitly by the caller's policy/model.
    """
    required = {
        "symbol",
        "time",
        "volume",
        "amount",
        "open",
        "high",
        "low",
        "close",
        "up_limit",
        "down_limit",
    }
    if not required <= set(bars):
        raise ValueError("missing stress input columns")
    result = bars.copy(deep=True).reset_index(drop=True)
    for index, row in bars.reset_index(drop=True).iterrows():
        if not isinstance(row.time, pd.Timestamp) or row.time.tzinfo is None:
            raise ValueError("aware clocks required")
        clock = row.time.tz_convert("UTC").isoformat()
        draw = keyed_uniform(scenario.seed, row.symbol, clock, "liquidity")
        multiplier = scenario.volume_multiplier * (1 - scenario.liquidity_jitter * draw)
        volume = math.floor(row.volume * multiplier)
        prices = {
            name: min(row.up_limit, max(row.down_limit, row[name] * scenario.price_multiplier))
            for name in ("open", "high", "low", "close")
        }
        base_vwap = row.amount / row.volume if row.volume else row.close
        vwap = min(prices["high"], max(prices["low"], base_vwap * scenario.price_multiplier))
        for name, value in prices.items():
            result.at[index, name] = value
        result.at[index, "volume"] = volume
        result.at[index, "amount"] = volume * vwap
    result.index = bars.index.copy()
    result.attrs["synthetic_stress"] = asdict(scenario)
    result.attrs["evidence"] = "uncalibrated_exogenous_scenario"
    return result
