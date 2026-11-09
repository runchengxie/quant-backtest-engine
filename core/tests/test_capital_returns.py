# Extracted from quant-platform/tests/test_capital_reconciliation.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.


import pytest

from quant_backtest_core.evidence.capital_returns import CapitalObservation, capital_performance


def test_external_money_cannot_become_alpha_and_fee_stays_a_loss():
    result = capital_performance(
        1000.0,
        0,
        [
            CapitalObservation(1, 1000.0, 1000.0, 2000.0),
            CapitalObservation(2, 1900.0, -500.0, 1400.0),
        ],
    )
    assert result["time_weighted_return"] == pytest.approx(-0.05)
    assert result["net_monetary_gain"] == pytest.approx(-100.0)
    assert result["net_external_flow"] == 500.0
    assert result["money_weighted_irr"] is None
    with pytest.raises(ValueError, match="flow identity"):
        capital_performance(1000.0, 0, [CapitalObservation(1, 1000.0, 100.0, 1200.0)])
    with pytest.raises(ValueError, match="positive"):
        capital_performance(1000.0, 0, [CapitalObservation(1, 1000.0, -1000.0, 0.0)])


def test_exact_linking_and_approximate_cash_weighting_are_distinct():
    result = capital_performance(
        1000.0,
        0,
        [CapitalObservation(1, 1100.0, 900.0, 2000.0), CapitalObservation(2, 2200.0, 0.0, 2200.0)],
    )
    assert result["time_weighted_return"] == pytest.approx(0.21)
    assert result["modified_dietz_return"] == pytest.approx(300 / 1450)
    with pytest.raises(ValueError, match="clock"):
        capital_performance(1000.0, 0, [CapitalObservation(0, 1000.0, 0.0, 1000.0)])


def test_capital_identity_has_no_absolute_money_floor():
    with pytest.raises(ValueError, match="flow identity"):
        capital_performance(1e-12, 0, [CapitalObservation(1, 1e-12, 0.0, 1e-10)])
