# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_minute_execution_hardening.py
"""Synthetic contract evidence through the supported compatibility entry point."""

import pandas as pd
import pytest
from test_minute_execution import bars, targets

from quant_backtest_core._minute.minute_execution import (
    MinuteExecutionConfig,
    simulate_minute_execution,
)


@pytest.mark.parametrize("order_type", ["limit", "stop", "stop_limit", "trailing_stop"])
def test_unsupported_path_dependent_orders_are_rejected(order_type):
    t = targets()
    t["order_type"] = order_type
    with pytest.raises(ValueError, match="order_type"):
        simulate_minute_execution(t, bars(), MinuteExecutionConfig(10000, 1, 0, 0))


@pytest.mark.parametrize("offset", [1, 60])
def test_information_must_be_available_by_decision(offset):
    t = targets()
    t["information_time"] = t.decision_time + pd.Timedelta(seconds=offset)
    with pytest.raises(ValueError, match="information_time"):
        simulate_minute_execution(t, bars(), MinuteExecutionConfig(10000, 1, 0, 0))


def test_explicit_market_and_known_information_preserve_default_results():
    t = targets()
    config = MinuteExecutionConfig(10000, 0.1, 0, 0)
    expected = simulate_minute_execution(t, bars(), config)
    t["order_type"] = "market"
    t["information_time"] = t.decision_time
    actual = simulate_minute_execution(t, bars(), config)
    pd.testing.assert_frame_equal(actual.fills, expected.fills)


def test_side_specific_touch_is_conservative_without_an_intrabar_path():
    b = bars()
    b.loc[1:, ["low", "high"]] = [9.5, 11]
    result = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 1, 0, 0))
    assert result.fills.empty
    assert result.orders.reason.tolist() == ["up_limit_touch"]


def test_fee_sensitivity_holds_quantity_constant_with_cash_headroom():
    t = targets(weights=(0.5,))
    low = simulate_minute_execution(t, bars(), MinuteExecutionConfig(10000, 0.1, 0, 0))
    high = simulate_minute_execution(t, bars(), MinuteExecutionConfig(10000, 0.1, 20, 20))
    assert low.fills.quantity.tolist() == high.fills.quantity.tolist() == [100, 100]
    assert high.summary["transaction_cost"] == 4
    assert low.daily.nav.iloc[-1] - high.daily.nav.iloc[-1] == 4
