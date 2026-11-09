# Extracted from quant-platform/tests/test_impact_optimization_scenarios.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
import pytest

from quant_backtest_core.backtest.impact_scenarios import linear_impact_scenario


def test_permanent_round_trip_conserves_quantity_without_manipulation_profit():
    result = linear_impact_scenario(
        [4, -1, -3], unaffected_price=100, permanent=0.5, temporary=0.1, fee_per_share=0.02
    )
    assert result.final_inventory == 0
    assert result.final_displacement == 0
    assert result.cash_change == pytest.approx(-2.76)
    assert sum(fill.quantity for fill in result.fills) == 0
    assert result.fills[0].execution_price == pytest.approx(101.4)


def test_splitting_preserves_linear_permanent_integral():
    first = linear_impact_scenario([4], unaffected_price=100, permanent=0.5)
    split = linear_impact_scenario([1, 3], unaffected_price=100, permanent=0.5)
    assert first.cash_change == split.cash_change == -404


@pytest.mark.parametrize(
    "kwargs",
    [
        {"permanent": -1},
        {"temporary": float("nan")},
        {"fee_per_share": -1},
        {"unaffected_price": 0},
    ],
)
def test_impact_rejects_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        linear_impact_scenario([1], **({"unaffected_price": 100} | kwargs))


@pytest.mark.parametrize("path", [[1, -1], [-2, 1, 1], [1, 3, -2, -2], [0, 2, -2]])
def test_permanent_only_round_trips_have_zero_cash_change(path):
    result = linear_impact_scenario(path, unaffected_price=100, permanent=0.5)
    assert result.cash_change == pytest.approx(0)
    assert result.final_inventory == 0
