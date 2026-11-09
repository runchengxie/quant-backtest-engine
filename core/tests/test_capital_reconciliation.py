from dataclasses import replace

import pytest

from quant_backtest_core.backtest.reconciliation import (
    AccountEvidence,
    OrderEvidence,
    reconcile_evidence,
)
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


def evidence():
    return AccountEvidence(
        "paper",
        "CNY",
        1,
        2,
        True,
        "local",
        100.0,
        {"A": 10},
        {"venue-order": OrderEvidence("A", 5, 10.0)},
        ("venue-fill",),
    )


def test_reconciliation_is_clocked_complete_read_only_and_source_explicit():
    local = evidence()
    external = replace(local, source_binding="supplied-external")
    assert reconcile_evidence(local, external, decision_ns=2)["status"] == "matched"
    changed = replace(external, cash=99.0, quantities={"A": 11}, orders={}, fill_ids=("unknown",))
    result = reconcile_evidence(local, changed, decision_ns=2)
    assert result["status"] == "blocked_mismatch"
    assert result["share_delta"] == {"A": 1}
    assert result["cash_delta"] == -1.0
    assert result["action"] == "halt_new_orders"
    assert local.cash == 100.0 and local.quantities == {"A": 10}
    assert (
        reconcile_evidence(local, replace(external, complete=False), decision_ns=2)["status"]
        == "blocked_evidence"
    )
    assert (
        reconcile_evidence(local, replace(external, available_ns=3), decision_ns=2)["status"]
        == "blocked_evidence"
    )
    assert (
        reconcile_evidence(local, replace(external, as_of_ns=0), decision_ns=2)["status"]
        == "blocked_evidence"
    )
    with pytest.raises(ValueError, match="integer"):
        replace(local, quantities={"A": 1.5})


def test_capital_identity_has_no_absolute_money_floor():
    with pytest.raises(ValueError, match="flow identity"):
        capital_performance(1e-12, 0, [CapitalObservation(1, 1e-12, 0.0, 1e-10)])


def test_reconciliation_overflow_blocks_without_nonfinite_json():
    import json

    local = replace(evidence(), cash=-1e308)
    external = replace(local, source_binding="external", cash=1e308)
    result = reconcile_evidence(local, external, decision_ns=2)
    assert result["status"] == "blocked_evidence"
    assert result["action"] == "halt_new_orders"
    json.dumps(result, allow_nan=False)


def test_fill_coverage_and_order_price_must_match():
    local = evidence()
    external = replace(local, source_binding="external", fill_window_start_ns=1)
    assert reconcile_evidence(local, external, decision_ns=2)["status"] == "blocked_evidence"
    external = replace(
        local, source_binding="external", orders={"venue-order": OrderEvidence("A", 5, 10.01)}
    )
    assert reconcile_evidence(local, external, decision_ns=2)["order_mismatches"] == ["venue-order"]
