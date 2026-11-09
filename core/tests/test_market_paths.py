# Extracted from quant-platform/tests/test_market_paths.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Synthetic hand cases for dependent return/liquidity resampling."""

import math
from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from quant_backtest_core.backtest.market_paths import (
    MarketPathSpec,
    fit_market_paths,
    generate_market_paths,
)


@pytest.fixture
def panel():
    rows = []
    # Two return observations: +10%, then -20%; one eligible length-two block.
    for time, close, volume in zip(
        pd.date_range("2026-01-01", periods=3, tz="UTC"),
        [10.0, 11.0, 8.8],
        [50, 100, 0],
        strict=True,
    ):
        for symbol, ratio in [("A", 1), ("B", 2)]:
            rows.append(
                {
                    "symbol": symbol,
                    "time": time,
                    "open": close * ratio * 0.95,
                    "high": close * ratio * 1.1,
                    "low": close * ratio * 0.9,
                    "close": close * ratio,
                    "volume": volume,
                    "amount": volume * close * ratio * 1.05,
                }
            )
    return pd.DataFrame(rows)


CUTOFF = pd.Timestamp("2026-01-03", tz="UTC")
CALENDAR = pd.date_range("2026-02-01", periods=4, tz="UTC")


def fitted(panel, block_length=2):
    return fit_market_paths(panel, CUTOFF, MarketPathSpec(block_length, seed=7))


def generate(model, calendar=CALENDAR, ids=("one",)):
    return generate_market_paths(model, calendar, ids, {"B": 200.0, "A": 100.0})


def test_common_blocks_match_hand_returns_ohlc_vwap_and_zero_volume(panel):
    path = generate(fitted(panel))["one"]
    a = path[path.symbol == "A"].reset_index(drop=True)
    b = path[path.symbol == "B"].reset_index(drop=True)
    assert a.close.tolist() == pytest.approx([110, 88, 96.8, 77.44])
    assert a.open.tolist() == pytest.approx([104.5, 83.6, 91.96, 73.568])
    assert a.high.tolist() == pytest.approx([121, 96.8, 106.48, 85.184])
    assert a.low.tolist() == pytest.approx([99, 79.2, 87.12, 69.696])
    assert a.volume.tolist() == [100, 0, 100, 0]
    assert a.amount.tolist() == pytest.approx([11550, 0, 10164, 0])
    assert b.close.tolist() == pytest.approx([220, 176, 193.6, 154.88])
    assert a.sampled_block_id.tolist() == b.sampled_block_id.tolist()
    assert a.block_offset.tolist() == [0, 1, 0, 1]
    assert a.block_boundary.tolist() == [True, False, True, False]
    assert a.source_time.tolist() == [panel.time.iloc[2], panel.time.iloc[4]] * 2
    assert (path[["open", "high", "low", "close"]] > 0).all().all()
    assert path.time.unique().tolist() == CALENDAR.tolist()
    assert path.attrs["synthetic"] is True
    assert path.attrs["execution_semantics"] == "absent: actions, limits, tradability"
    assert path.attrs["scope"] == "conditional_moving_block_return_liquidity"
    assert path.event_id.is_unique


def test_future_rows_order_and_batching_do_not_change_frozen_prefix(panel):
    source = panel.copy(deep=True)
    model = fitted(panel)
    future = panel.iloc[-2:].assign(time=pd.Timestamp("2026-01-10", tz="UTC"), close=-9)
    other = fitted(pd.concat([future, panel.iloc[::-1]], ignore_index=True))
    assert model == other
    original = generate(model)["one"]
    pd.testing.assert_frame_equal(original, generate(other)["one"])
    pd.testing.assert_frame_equal(
        original.iloc[:4].reset_index(drop=True),
        generate(model, CALENDAR[:2], ("two", "one"))["one"],
    )
    pd.testing.assert_frame_equal(original, generate(model, ids=("two", "one"))["one"])
    assert original.to_json(date_format="iso") == generate(model)["one"].to_json(date_format="iso")
    pd.testing.assert_frame_equal(panel, source)
    with pytest.raises(FrozenInstanceError):
        model.source_hash = "changed"
    panel.loc[:, "close"] = -1
    pd.testing.assert_frame_equal(original, generate(model)["one"])


def test_multiple_eligible_blocks_share_draws_and_preserve_within_block_order(panel):
    extra = panel.iloc[-2:].copy()
    extra["time"] = pd.Timestamp("2026-01-04", tz="UTC")
    extra[["open", "high", "low", "close", "amount"]] *= 1.25
    extra["volume"] = 25
    extra["amount"] = extra.close * extra.volume
    model = fit_market_paths(pd.concat([panel, extra]), extra.time.iloc[0], MarketPathSpec(2, 9))
    path = generate(model, pd.date_range("2026-02-01", periods=32, tz="UTC"))["one"]
    assert path.loc[path.block_boundary, "source_time"].nunique() == 2
    for _, block in path.groupby("sampled_block_id"):
        a = block[block.symbol == "A"]
        b = block[block.symbol == "B"]
        assert a.source_time.tolist() == b.source_time.tolist()
        assert a.source_time.iloc[1] - a.source_time.iloc[0] == pd.Timedelta(days=1)
    different = generate(model, ids=("one", "two"))
    assert different["one"].event_id.tolist() != different["two"].event_id.tolist()


@pytest.mark.parametrize(
    "change,match",
    [
        ("duplicate", "duplicate"),
        ("zero_price", "price"),
        ("negative_volume", "volume"),
        ("zero_volume_amount", "zero volume"),
        ("bad_vwap", "VWAP"),
        ("bad_ohlc", "OHLC"),
        ("nan", "finite"),
        ("naive", "aware"),
        ("symbol", "symbol"),
    ],
)
def test_invalid_training_evidence_is_rejected_without_clipping(panel, change, match):
    if change == "duplicate":
        panel = pd.concat([panel, panel.iloc[:1]])
    elif change == "zero_price":
        panel.loc[0, "close"] = 0
    elif change == "negative_volume":
        panel.loc[0, "volume"] = -1
    elif change == "zero_volume_amount":
        panel.loc[4, "amount"] = 1
    elif change == "bad_vwap":
        panel.loc[0, "amount"] = 10000
    elif change == "bad_ohlc":
        panel.loc[0, "high"] = 1
    elif change == "nan":
        panel.loc[0, "close"] = float("nan")
    elif change == "naive":
        panel["time"] = panel.time.dt.tz_localize(None)
    elif change == "symbol":
        panel.loc[0, "symbol"] = ""
    with pytest.raises(ValueError, match=match):
        fitted(panel)


@pytest.mark.parametrize(
    "kwargs", [{"block_length": 0}, {"seed": True}, {"missing_policy": "fill"}]
)
def test_unsupported_spec_is_rejected(kwargs):
    with pytest.raises(ValueError):
        MarketPathSpec(**({"block_length": 2, "seed": 7} | kwargs))


def test_short_history_and_naive_cutoff_are_rejected(panel):
    with pytest.raises(ValueError, match="block"):
        fitted(panel, block_length=3)
    with pytest.raises(ValueError, match="aware"):
        fit_market_paths(panel, CUTOFF.tz_localize(None), MarketPathSpec(2, 7))


@pytest.mark.parametrize(
    "calendar,ids,prices,match",
    [
        (CALENDAR, ["one"], {"A": 100, "C": 200}, "symbols"),
        (CALENDAR, ["one"], {"A": 0, "B": 200}, "positive"),
        (CALENDAR, ["one", "one"], {"A": 100, "B": 200}, "scenario"),
        (CALENDAR[::-1], ["one"], {"A": 100, "B": 200}, "increasing"),
        ([CALENDAR[0], CALENDAR[0]], ["one"], {"A": 100, "B": 200}, "increasing"),
        (CALENDAR.tz_localize(None), ["one"], {"A": 100, "B": 200}, "aware"),
        ([CUTOFF], ["one"], {"A": 100, "B": 200}, "cutoff"),
    ],
)
def test_invalid_generation_contract_is_rejected(panel, calendar, ids, prices, match):
    with pytest.raises(ValueError, match=match):
        generate_market_paths(fitted(panel), calendar, ids, prices)


def test_missing_balanced_observation_is_rejected(panel):
    with pytest.raises(ValueError, match="balanced"):
        fitted(panel.drop(index=1))


def test_changed_initial_anchor_cannot_alias_financial_path_evidence(panel):
    model = fitted(panel)
    original = generate(model)["one"]
    changed = generate_market_paths(model, CALENDAR, ["one"], {"A": 50, "B": 100})["one"]
    assert changed.close.tolist() == pytest.approx([55, 110, 44, 88, 48.4, 96.8, 38.72, 77.44])
    assert original.event_id.tolist() != changed.event_id.tolist()
    assert original.attrs["generation_hash"] != changed.attrs["generation_hash"]
    assert original.attrs["model_hash"] == changed.attrs["model_hash"]
    # Mapping insertion order does not define a different anchor contract.
    reordered = generate_market_paths(model, CALENDAR, ["one"], {"A": 100, "B": 200})["one"]
    pd.testing.assert_frame_equal(original, reordered)


@pytest.mark.parametrize("anchor", [0.1, 0.2, 0.3, 0.7, 1e-100, 1e100])
def test_flat_generated_vwap_allows_only_bounded_float_roundoff(anchor):
    source = pd.DataFrame(
        [
            {
                "symbol": "A",
                "time": time,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 3.0,
                "amount": 3.0,
            }
            for time in pd.date_range("2026-01-01", periods=2, tz="UTC")
        ]
    )
    model = fit_market_paths(source, source.time.iloc[-1], MarketPathSpec(1, 7))
    path = generate_market_paths(model, CALENDAR, ["rounding"], {"A": anchor})["rounding"]
    assert path.close.tolist() == [anchor] * 4
    assert path.open.tolist() == path.high.tolist() == path.low.tolist() == [anchor] * 4
    assert path.volume.tolist() == [3.0] * 4
    assert path.amount.tolist() == pytest.approx([3 * anchor] * 4)
    vwap = path.amount / path.volume
    assert vwap.between(
        math.nextafter(anchor, -math.inf, steps=4),
        math.nextafter(anchor, math.inf, steps=4),
    ).all()
    prefix = generate_market_paths(model, CALENDAR[:2], ["other", "rounding"], {"A": anchor})
    pd.testing.assert_frame_equal(path.iloc[:2].reset_index(drop=True), prefix["rounding"])


@pytest.mark.parametrize("amount", [math.nextafter(3.0, math.inf), 3.03])
def test_source_vwap_outside_flat_bar_remains_strictly_rejected(amount):
    source = pd.DataFrame(
        [
            {
                "symbol": "A",
                "time": time,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 3.0,
                "amount": amount,
            }
            for time in pd.date_range("2026-01-01", periods=2, tz="UTC")
        ]
    )
    with pytest.raises(ValueError, match="VWAP"):
        fit_market_paths(source, source.time.iloc[-1], MarketPathSpec(1, 7))


@pytest.mark.parametrize("volume,anchor", [(1e-308, 1e-308), (0.5, 1.5e-323)])
def test_material_generated_vwap_roundoff_is_rejected_without_clipping(volume, anchor):
    source = pd.DataFrame(
        [
            {
                "symbol": "A",
                "time": time,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": volume,
                "amount": volume,
            }
            for time in pd.date_range("2026-01-01", periods=2, tz="UTC")
        ]
    )
    model = fit_market_paths(source, source.time.iloc[-1], MarketPathSpec(1, 7))
    # First case loses all amount to underflow. Second has a one-ULP VWAP
    # error but a material relative discrepancy near zero; the relative cap
    # must reject it even though a four-ULP-only check would accept it.
    with pytest.raises(ValueError, match="VWAP"):
        generate_market_paths(model, CALENDAR, ["underflow"], {"A": anchor})


def test_model_cutoff_seed_and_consumed_source_mutation_change_digest(panel):
    original = fitted(panel, block_length=1)
    seed = fit_market_paths(panel, CUTOFF, MarketPathSpec(1, 8))
    cutoff = fit_market_paths(panel, CUTOFF + pd.Timedelta(seconds=1), MarketPathSpec(1, 7))
    changed = panel.copy(deep=True)
    changed.loc[0, "volume"] = 25
    changed.loc[0, "amount"] = 262.5
    consumed = fitted(changed, block_length=1)
    assert seed.source_hash == cutoff.source_hash == original.source_hash
    assert len({original.model_hash, seed.model_hash, cutoff.model_hash, consumed.model_hash}) == 4
    assert consumed.source_hash != original.source_hash
    assert generate(original)["one"].event_id.tolist() != generate(seed)["one"].event_id.tolist()
    assert generate(original)["one"].event_id.tolist() != generate(cutoff)["one"].event_id.tolist()
