from decimal import Decimal as D

import pytest
from test_minute_execution import bars, targets

from quant_backtest_core.backtest.execution_policies import checkpoint_sides, proportional_lots
from quant_backtest_core.backtest.minute import MinuteExecutionConfig, simulate_minute_execution
from quant_backtest_core.microstructure.historical_projection import TradeTape, sweep_depth


def test_forecast_vwap_releases_more_when_expected_volume_is_higher():
    data = bars(("2026-01-05 09:29", "2026-01-05 09:31", "2026-01-05 09:34"), volume=10000)
    common = dict(release_slices=2, execution_minutes=6, latency_minutes=0)
    twap = simulate_minute_execution(
        targets(), data, MinuteExecutionConfig(10000, 1, 0, 0, **common)
    )
    vwap = simulate_minute_execution(
        targets(),
        data,
        MinuteExecutionConfig(10000, 1, 0, 0, forecast_slice_weights=(1, 4), **common),
    )
    assert twap.fills.quantity.tolist() == [500, 500]
    assert vwap.fills.quantity.tolist() == [200, 800]


def test_checkpoint_and_lot_allocation():
    assert checkpoint_sides({"buy": D(".9"), "sell": D(".7")}, D(".8")) == ("sell",)
    assert proportional_lots({"a": 4, "b": 6, "c": 8}, 6) == {"a": 1, "b": 2, "c": 3}
    assert proportional_lots({"a": 1, "b": 1}, 1) == {"a": 1, "b": 0}
    with pytest.raises(ValueError):
        proportional_lots({"a": -1}, 1)


def test_historical_projections_keep_decimal_notional():
    tape = TradeTape.build([19, 20], [100000, 110000])
    outcome = tape.project(0, 2, D(2), D(".05"), D(10000))
    assert D(outcome["projected_notional_cny"]) == D("20.50")
    assert sweep_depth([(D(10), 1), (D(11), 1)], D(2))["visible_notional_cny"] == "21"
