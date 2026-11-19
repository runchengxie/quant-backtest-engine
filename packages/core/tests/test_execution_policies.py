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


def test_cash_allocation_uses_distinct_fee_inclusive_lot_costs():
    from quant_backtest_core.backtest.execution_policies import BuyLotRequest, allocate_buy_lots

    requests = {
        "a": BuyLotRequest(4, D("12.50"), D(100)),
        "b": BuyLotRequest(4, D("5.00"), D(200)),
    }
    assert allocate_buy_lots(requests, D(25), "fixed") == {"a": 2, "b": 0}
    assert allocate_buy_lots(requests, D(25), "pro_rata") == {"a": 1, "b": 2}
    assert allocate_buy_lots(requests, D(25), "largest_gap") == {"a": 0, "b": 4}
    assert allocate_buy_lots(requests, D("4.99"), "fixed") == {"a": 0, "b": 0}
    with pytest.raises(ValueError):
        BuyLotRequest(1, D(0))


def test_weighted_release_preserves_fractional_parent_and_rounds_down():
    from quant_backtest_core.backtest.execution_policies import released_quantity

    assert released_quantity(D("1050"), 100, (6598, 3402), 1) == 600
    assert released_quantity(D("1050"), 100, (6598, 3402), 2) == 1000
    assert released_quantity(D("195"), 100, (9, 1), 1) == 100
    with pytest.raises(ValueError):
        released_quantity(D(100), 100, (3, 7), 3)
