# Extracted from quant-platform/packages/platform/src/quant_platform/backtest/market_paths.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Frozen, uncalibrated common-block return and liquidity resampling.

These paths carry no execution contract. Consumers must declare actions, limits
and tradability and recompute features before using the existing account owner.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

import pandas as pd

_VERSION = "common-moving-block.v1"
_FIELDS = ("open", "high", "low", "close", "volume", "amount")
_UNITS = (("price", "raw_quote_per_share"), ("volume", "shares"), ("amount", "quote"))
_SCOPE = "conditional_moving_block_return_liquidity"


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _clock(value: pd.Timestamp) -> pd.Timestamp:
    if not isinstance(value, pd.Timestamp) or value.tzinfo is None or pd.isna(value):
        raise ValueError("finite timezone-aware Timestamp clocks required")
    return value.tz_convert("UTC")


@dataclass(frozen=True)
class MarketPathSpec:
    block_length: int
    seed: int
    missing_policy: str = "reject"

    def __post_init__(self):
        if type(self.block_length) is not int or self.block_length <= 0:
            raise ValueError("block_length must be a positive integer")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if self.missing_policy != "reject":
            raise ValueError("only missing_policy='reject' is supported")


@dataclass(frozen=True)
class FrozenPathModel:
    """Immutable canonical training snapshot; no mutable DataFrame is retained."""

    spec: MarketPathSpec
    cutoff: pd.Timestamp
    symbols: tuple[str, ...]
    source_times: tuple[str, ...]
    # Each clock holds canonical assets, each asset holds _FIELDS in order.
    bars: tuple[tuple[tuple[float, ...], ...], ...]
    source_hash: str
    model_hash: str
    generator_version: str = _VERSION
    units: tuple[tuple[str, str], ...] = _UNITS


def _validate_vwap(vwap: float, low: float, high: float, *, generated: bool) -> None:
    if low <= vwap <= high:
        return
    if generated and math.isfinite(vwap) and vwap > 0:
        boundary = low if vwap < low else high
        # Scaling amount and dividing by volume round separately from scaling
        # the price boundary. Allow only local arithmetic drift, never clip it.
        # The relative cap also prevents large allowances near subnormal zero.
        if abs(vwap - boundary) <= 4 * math.ulp(boundary) and math.isclose(
            vwap, boundary, rel_tol=8 * math.ulp(1.0), abs_tol=0.0
        ):
            return
    raise ValueError("VWAP must be inside OHLC range")


def _validate_bar(values: tuple[float, ...], *, generated: bool = False) -> None:
    opening, high, low, close, volume, amount = values
    if not all(math.isfinite(value) for value in values):
        raise ValueError("all OHLC, volume and amount must be finite")
    if min(opening, high, low, close) <= 0:
        raise ValueError("prices must be positive")
    if not low <= min(opening, close) <= max(opening, close) <= high:
        raise ValueError("incoherent OHLC range")
    if volume < 0 or amount < 0:
        raise ValueError("volume and amount must be nonnegative")
    if volume == 0:
        if amount != 0:
            raise ValueError("zero volume requires zero amount")
    else:
        _validate_vwap(amount / volume, low, high, generated=generated)


def fit_market_paths(
    training_panel: pd.DataFrame, cutoff: pd.Timestamp, spec: MarketPathSpec
) -> FrozenPathModel:
    """Bind only rows available at cutoff, requiring a complete aligned panel.

    The first clock is an anchor, not a sampled return. Observations thereafter
    use the preceding close. Fixed-length moving blocks never wrap source time.
    """
    cutoff = _clock(cutoff)
    if not isinstance(spec, MarketPathSpec):
        raise ValueError("MarketPathSpec required")
    if not {"symbol", "time", *_FIELDS} <= set(training_panel):
        raise ValueError("missing market path input columns")
    clocks = training_panel.time.map(_clock)
    allowed = training_panel.loc[clocks <= cutoff, ["symbol", "time", *_FIELDS]].copy()
    allowed["time"] = clocks.loc[clocks <= cutoff]
    if allowed.empty:
        raise ValueError("training panel is empty at cutoff")
    if any(not isinstance(s, str) or not s.strip() for s in allowed.symbol):
        raise ValueError("nonempty string symbols required")
    if allowed.duplicated(["time", "symbol"]).any():
        raise ValueError("duplicate symbol clocks")
    symbols = tuple(sorted(allowed.symbol.unique()))
    times = tuple(sorted(allowed.time.unique()))
    if len(allowed) != len(times) * len(symbols):
        raise ValueError("balanced panel required; missing observations are not imputed")
    if len(times) <= spec.block_length:
        raise ValueError("not enough return observations for block_length")
    allowed = allowed.sort_values(["time", "symbol"])
    values = []
    for row in allowed.loc[:, _FIELDS].itertuples(index=False, name=None):
        try:
            numeric = tuple(float(value) for value in row)
        except (TypeError, ValueError) as exc:
            raise ValueError("finite numeric OHLC, volume and amount required") from exc
        _validate_bar(numeric)
        values.append(numeric)
    bars = tuple(
        tuple(values[start : start + len(symbols)]) for start in range(0, len(values), len(symbols))
    )
    source_times = tuple(time.isoformat() for time in times)
    source_hash = _digest([symbols, source_times, bars])
    model_hash = _digest([_VERSION, source_hash, cutoff.isoformat(), asdict(spec), _UNITS, symbols])
    return FrozenPathModel(spec, cutoff, symbols, source_times, bars, source_hash, model_hash)


def _generate_one(
    model: FrozenPathModel,
    clocks: tuple[pd.Timestamp, ...],
    scenario_id: str,
    initial_prices: Mapping[str, float],
) -> pd.DataFrame:
    anchors = {symbol: float(initial_prices[symbol]) for symbol in model.symbols}
    generation_hash = _digest([model.model_hash, scenario_id, anchors])
    previous = list(anchors.values())
    rows = []
    block_length = model.spec.block_length
    possible_starts = len(model.bars) - block_length
    for ordinal, time in enumerate(clocks):
        block_number, offset = divmod(ordinal, block_length)
        key = [
            model.generator_version,
            model.model_hash,
            model.spec.seed,
            scenario_id,
            block_number,
        ]
        start = int(_digest(key), 16) % possible_starts + 1
        source_index = start + offset
        block_id = _digest([*key, start])
        for asset, symbol in enumerate(model.symbols):
            sampled = model.bars[source_index][asset]
            scale = previous[asset] / model.bars[source_index - 1][asset][3]
            prices = [value * scale for value in sampled[:4]]
            volume = sampled[4]
            amount = sampled[5] * scale
            _validate_bar((*prices, volume, amount), generated=True)
            previous[asset] = prices[3]
            rows.append(
                dict(
                    symbol=symbol,
                    time=time,
                    **dict(zip(_FIELDS, (*prices, volume, amount), strict=True)),
                    event_id=_digest([generation_hash, ordinal, time.isoformat(), symbol]),
                    sampled_block_id=block_id,
                    source_time=pd.Timestamp(model.source_times[source_index]),
                    block_offset=offset,
                    block_boundary=offset == 0,
                )
            )
    frame = pd.DataFrame(rows)
    frame.attrs = {
        "synthetic": True,
        "evidence": "uncalibrated_generator_scenario",
        "scope": _SCOPE,
        "execution_semantics": "absent: actions, limits, tradability",
        "continuity": "source continuity only within blocks; lost at block boundaries",
        "generator_version": model.generator_version,
        "source_hash": model.source_hash,
        "model_hash": model.model_hash,
        "generation_hash": generation_hash,
        "fit_cutoff": model.cutoff.isoformat(),
        "units": dict(model.units),
        "seed": model.spec.seed,
        "scenario_id": scenario_id,
        "block_length": block_length,
        "missing_policy": model.spec.missing_policy,
        "vwap_coherence": "source_exact; generated_4_boundary_ulps_and_8_machine_eps_relative",
        "initial_prices": anchors,
        "clock_semantics": "time is availability; source_time is sampled training availability",
    }
    return frame


def generate_market_paths(
    model: FrozenPathModel,
    calendar: Sequence[pd.Timestamp],
    scenario_ids: Sequence[str],
    initial_prices: Mapping[str, float],
) -> dict[str, pd.DataFrame]:
    """Generate independent scenario-keyed paths with shared block draws per asset.

    Calendar extension preserves prefixes. Scenario order/batching and mapping
    insertion order never enter a draw key. Initial prices anchor preceding closes.
    No post-cutoff observations, fitting, matching or cash accounting occur here.
    """
    clocks = tuple(_clock(time) for time in calendar)
    if not clocks:
        raise ValueError("nonempty calendar required")
    if any(left >= right for left, right in itertools.pairwise(clocks)):
        raise ValueError("calendar must be strictly increasing with unique clocks")
    if clocks[0] <= model.cutoff:
        raise ValueError("generation must begin after fit cutoff")
    ids = tuple(scenario_ids)
    if any(not isinstance(s, str) or not s.strip() for s in ids) or len(set(ids)) != len(ids):
        raise ValueError("unique nonempty scenario identities required")
    if set(initial_prices) != set(model.symbols):
        raise ValueError("initial price symbols must equal fitted symbols")
    try:
        valid = all(math.isfinite(float(p)) and float(p) > 0 for p in initial_prices.values())
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("initial prices must be finite and positive")
    return {
        scenario_id: _generate_one(model, clocks, scenario_id, initial_prices)
        for scenario_id in ids
    }
