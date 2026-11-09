# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/_portfolio/_minute_validation.py
# Original SHA256: a7c6f3784db7e22b7ec424d912c5eeaadcb9522f8da2a92d5a767ca30662b471
"""Input validation shared by the minute reference simulator."""

import math

import pandas as pd


def _validate(targets, bars):
    required = {
        "symbol",
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "up_limit",
        "down_limit",
        "tradable",
    }
    if not required <= set(bars) or not {"decision_time", "entry_time", "symbol", "weight"} <= set(
        targets
    ):
        raise ValueError("missing required columns")
    for frame, cols in ((bars, ["time"]), (targets, ["decision_time", "entry_time"])):
        if frame.isna().any().any():
            raise ValueError("null inputs")
        for col in cols:
            if any(not isinstance(t, pd.Timestamp) or t.tzinfo is None for t in frame[col]):
                raise ValueError("timestamps must be timezone aware pandas Timestamps")
        if any(not isinstance(s, str) or not s.strip() for s in frame.symbol):
            raise ValueError("invalid symbol")
    if (
        bars.duplicated(["symbol", "time"]).any()
        or targets.duplicated(["symbol", "entry_time"]).any()
    ):
        raise ValueError("duplicate bars or targets")
    _validate_intervals(bars)
    _validate_bar_numbers(bars)
    _validate_target_weights(targets)
    _validate_mark_provenance(bars)


def _validate_mark_provenance(bars):
    columns = {"mark_source_time", "mark_basis"}
    if not columns.intersection(bars.columns):
        return
    if not columns <= set(bars.columns):
        raise ValueError("mark_source_time and mark_basis must be provided together")
    if any(not isinstance(t, pd.Timestamp) or t.tzinfo is None for t in bars.mark_source_time):
        raise ValueError("mark_source_time must be timezone aware pandas Timestamps")
    if (bars.mark_source_time > bars.time).any():
        raise ValueError("mark_source_time must not follow bar time")
    if not bars.mark_basis.isin(["raw", "declared_nontrading"]).all():
        raise ValueError("unsupported mark_basis")
    raw = bars.mark_basis.eq("raw")
    if (bars.loc[raw, "mark_source_time"] != bars.loc[raw, "time"]).any():
        raise ValueError("raw mark source time must equal bar time")
    declared = ~raw
    if (
        bars.loc[declared, "tradable"]
        | bars.loc[declared, "volume"].ne(0)
        | bars.loc[declared, "amount"].ne(0)
    ).any():
        raise ValueError("declared nontrading marks cannot trade or carry volume/amount")
    prices = bars.loc[declared, ["open", "high", "low", "close"]]
    if not prices.eq(prices["close"], axis=0).all().all():
        raise ValueError("declared nontrading marks must have one flat price")


def _validate_intervals(bars):
    if "interval_start" not in bars:
        return
    if any(not isinstance(t, pd.Timestamp) or t.tzinfo is None for t in bars.interval_start):
        raise ValueError("interval_start must be timezone aware")
    if (bars.interval_start >= bars.time).any():
        raise ValueError("interval_start must precede time")


def _validate_bar_numbers(bars):
    numbers = bars[["open", "high", "low", "close", "volume", "amount", "up_limit", "down_limit"]]
    if not numbers.map(lambda x: isinstance(x, (int, float)) and math.isfinite(x)).all().all():
        raise ValueError("nonfinite numeric bars")
    if (numbers < 0).any().any() or (
        bars[["open", "high", "low", "close", "up_limit", "down_limit"]] <= 0
    ).any().any():
        raise ValueError("invalid price or volume")
    if (
        (bars.low > bars[["open", "close"]].min(axis=1))
        | (bars.high < bars[["open", "close"]].max(axis=1))
        | (bars.low > bars.high)
    ).any():
        raise ValueError("inconsistent OHLC")
    if any(type(v) is not bool for v in bars.tradable):
        raise ValueError("tradable must be boolean")


def _validate_target_weights(targets):
    if "order_type" in targets and not targets.order_type.eq("market").all():
        raise ValueError("order_type must be market; intrabar conditional orders are unsupported")
    if "information_time" in targets:
        if any(
            not isinstance(t, pd.Timestamp) or t.tzinfo is None for t in targets.information_time
        ):
            raise ValueError("information_time must be timezone aware pandas Timestamps")
        if (targets.information_time > targets.decision_time).any():
            raise ValueError("information_time must be at or before decision_time")
    if not targets.weight.map(lambda x: math.isfinite(x) and 0 <= x <= 1).all():
        raise ValueError("invalid weight")
    if (targets.entry_time <= targets.decision_time).any():
        raise ValueError("entry must be after decision")
    if (targets.groupby("entry_time").weight.sum() > 1 + 1e-10).any():
        raise ValueError("weights exceed one")
    if (targets.groupby("entry_time").decision_time.nunique() != 1).any():
        raise ValueError("one decision time required per rebalance")
