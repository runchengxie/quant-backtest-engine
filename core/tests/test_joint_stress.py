# Extracted from quant-platform/tests/test_joint_stress.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
import pandas as pd
import pytest

from quant_backtest_core.backtest.stress import JointStress, keyed_uniform, stress_bars


def test_keyed_randomness_is_order_independent_and_stream_specific():
    first = keyed_uniform(7, "A", "clock", "depth")
    keyed_uniform(7, "B", "another-clock", "depth")
    assert first == keyed_uniform(7, "A", "clock", "depth")
    assert first != keyed_uniform(7, "A", "clock", "latency")


def test_stress_preserves_inputs_limits_and_turnover_units():
    source = bars()
    original = source.copy(deep=True)
    shock = JointStress("crisis", seed=7, price_multiplier=0.8, volume_multiplier=0.1)
    changed = stress_bars(source, shock)
    pd.testing.assert_frame_equal(source, original)
    assert changed.low.min() >= 9
    assert changed.high.max() <= 11
    assert changed.volume.max() <= 100
    assert (changed.amount == changed.volume * 9).all()
    reordered = stress_bars(source.iloc[::-1], shock).sort_index()
    pd.testing.assert_frame_equal(changed, reordered)


@pytest.mark.parametrize("kwargs", [{"volume_multiplier": -1}, {"risk_multiplier": 0}])
def test_bad_stress_rejected(kwargs):
    with pytest.raises(ValueError):
        JointStress("bad", **kwargs)


def bars(
    times=("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:33"), price=10.0, volume=1000
):
    return pd.DataFrame(
        [
            {
                "time": pd.Timestamp(t, tz="Asia/Shanghai"),
                "interval_start": pd.Timestamp(t, tz="Asia/Shanghai") - pd.Timedelta(seconds=30),
                "symbol": "A",
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "amount": price * volume,
                "up_limit": 11.0,
                "down_limit": 9.0,
                "tradable": True,
            }
            for t in times
        ]
    )
