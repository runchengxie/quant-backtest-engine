# Extracted from quant-platform/tests/test_transaction_costs.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Hand calculations catch double debits, lost orders and unsupported cost evidence."""

import importlib
import importlib.util

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from quant_backtest_core.evidence.cost_scope import fit_cost_scope, validate_cost_scope


def parents(**changes):
    row = {
        "parent_id": "p",
        "side": "buy",
        "requested_shares": 100,
        "reference_price": 10,
        "reference_ns": 1,
        "reference_available_ns": 2,
        "decision_ns": 3,
        "arrival_price": 10.1,
        "arrival_ns": 4,
        "arrival_available_ns": 5,
        "completed_ns": 10,
        "available_ns": 20,
        "status": "completed",
        "source_binding": "synthetic-source-v1",
        "evidence_kind": "synthetic",
        "quantity_unit": "shares",
        "currency": "CNY",
        "price_convention": "includes_spread_and_impact",
        "brokerage_terms_version": "fixture-v1",
        "opportunity_price": 10.5,
        "opportunity_ns": 15,
        "opportunity_available_ns": 16,
        "opportunity_benchmark": "terminal_mid",
        "market_volume_shares": 1000,
        "market_amount_cny": 10000,
        "liquidity_start_ns": 4,
        "liquidity_end_ns": 10,
        "liquidity_available_ns": 12,
        "liquidity_quantity_unit": "shares",
        "liquidity_amount_unit": "CNY",
        "liquidity_bucket": "liquid",
        "execution_minutes": 30,
        "cluster_id": "2026-01-01",
    }
    row.update(changes)
    return pd.DataFrame([row])


def fills(**changes):
    row = {
        "fill_id": "f1",
        "parent_id": "p",
        "child_id": "c1",
        "price": 10.2,
        "shares": 40,
        "fill_ns": 6,
        "receipt_ns": 7,
        "source_binding": "synthetic-source-v1",
        "evidence_kind": "synthetic",
        "quantity_unit": "shares",
        "currency": "CNY",
    }
    row.update(changes)
    return pd.DataFrame([row])


def audit(p=None, f=None, **terms):
    # Failure is an assertion about the missing public behavior, not a collection error.
    name = "quant_backtest_core.evidence.transaction_costs"
    assert importlib.util.find_spec(name) is not None, "transaction cost audit API is missing"
    api = importlib.import_module(name)
    return api.audit_transaction_costs(
        parents() if p is None else p,
        fills() if f is None else f,
        **(
            {"billing": "parent", "commission_bps": 3, "minimum_commission": 5, "sell_tax_bps": 10}
            | terms
        ),
    )


def test_buy_partial_costs_are_signed_and_fees_debited_only_once():
    p, f = parents(), fills()
    before_p, before_f = p.copy(deep=True), f.copy(deep=True)
    report = audit(p, f)
    row = report.parents.iloc[0]
    assert row.filled_shares == 40
    assert row.completion == 0.4
    assert row.modeled_commission == 5
    assert row.modeled_tax == 0
    assert row.modeled_cash_fees == 5
    assert row.recorded_cash_fees is None
    assert row.fee_evidence == "unavailable"
    assert row.reference_price_shortfall == pytest.approx(8)
    assert row.arrival_price_shortfall == pytest.approx(4)
    assert row.delay_shortfall == pytest.approx(4)
    assert row.reference_shortfall_with_modeled_fees == pytest.approx(13)
    assert row.opportunity_shortfall == pytest.approx(30)
    assert row.participation == 0.04
    assert not row.attribution_additive
    assert report.real_calibration == "unavailable"
    assert_frame_equal(p, before_p)
    assert_frame_equal(f, before_f)


def test_sell_improvement_and_recorded_fees_are_distinct_from_model():
    report = audit(parents(side="sell"), fills(recorded_commission=1.25, recorded_tax=0.41))
    row = report.parents.iloc[0]
    assert row.reference_price_shortfall == pytest.approx(-8)
    assert row.arrival_price_shortfall == pytest.approx(-4)
    assert row.delay_shortfall == pytest.approx(-4)
    assert row.opportunity_shortfall == pytest.approx(-30)
    assert row.modeled_tax == 0.41
    assert row.modeled_cash_fees == 5.41
    assert row.recorded_cash_fees == 1.66
    assert row.reference_shortfall_with_recorded_fees == pytest.approx(-6.34)
    assert row.fee_evidence == "caller_recorded"


def test_parent_minimum_once_child_minimum_twice_and_reordered_reports_deduplicate():
    two = pd.concat(
        [fills(), fills(fill_id="f2", child_id="c2", shares=60, fill_ns=8, receipt_ns=9)]
    )
    duplicate = pd.concat([two.iloc[::-1], fills(receipt_ns=19)], ignore_index=True)
    parent = audit(f=duplicate)
    assert parent.parents.iloc[0].modeled_commission == 5
    assert len(parent.fills) == 2
    assert parent.duplicate_reports == 1
    assert parent.fills.iloc[0].receipt_ns == 7
    assert audit(f=two, billing="child").parents.iloc[0].modeled_commission == 10
    assert parent.source_digest == audit(f=duplicate.iloc[::-1]).source_digest


def test_cents_half_up_and_equivalent_price_debit_do_not_charge_spread_twice():
    # 10.05 * 100 * 5bps = 0.5025 -> 0.50. Price shortfall is 5, total is 5.50.
    row = audit(
        parents(requested_shares=100, arrival_price=10),
        fills(price=10.05, shares=100),
        commission_bps=5,
        minimum_commission=0,
    ).parents.iloc[0]
    assert row.modeled_commission == 0.5
    assert row.reference_shortfall_with_modeled_fees == pytest.approx(5.5)
    # Equivalent cash fee 0.50 / 100 shares shifts execution price by 0.005 exactly once.
    embedded = audit(
        parents(requested_shares=100),
        fills(price=10.055, shares=100),
        commission_bps=0,
        minimum_commission=0,
    ).parents.iloc[0]
    assert embedded.reference_shortfall_with_modeled_fees == pytest.approx(5.5)
    half = audit(f=fills(price=10.05, shares=1), commission_bps=100, minimum_commission=0)
    assert half.parents.iloc[0].modeled_commission == 0.10
    half_up = audit(f=fills(price=10.5, shares=1), commission_bps=100, minimum_commission=0)
    assert half_up.parents.iloc[0].modeled_commission == 0.11


def test_cancelled_zero_fill_preserved_and_opportunity_is_descriptive():
    p = parents(status="cancelled")
    empty = fills().iloc[:0]
    row = audit(p, empty).parents.iloc[0]
    assert row.completion == 0
    assert row.modeled_cash_fees == 0
    assert row.opportunity_shortfall == 50
    assert row.reference_price_shortfall == 0
    assert audit(p, empty).cost_observations(fee_basis="modeled").empty
    changed = audit(parents(opportunity_price=12), fills()).parents.iloc[0]
    assert changed.opportunity_shortfall == 120
    assert changed.modeled_cash_fees == 5
    assert changed.reference_shortfall_with_modeled_fees == pytest.approx(13)


def test_missing_quotes_and_liquidity_remain_unavailable_not_zero():
    p = parents(
        arrival_price=None,
        arrival_ns=None,
        arrival_available_ns=None,
        opportunity_price=None,
        opportunity_ns=None,
        opportunity_available_ns=None,
        market_volume_shares=None,
    )
    row = audit(p).parents.iloc[0]
    assert row.arrival_price_shortfall is None
    assert row.delay_shortfall is None
    assert row.opportunity_shortfall is None
    assert row.participation is None
    assert set(row.unavailable_reasons) >= {"arrival_quote", "opportunity_benchmark", "liquidity"}
    assert audit(p).cost_observations(fee_basis="modeled").empty


@pytest.mark.parametrize(
    "column,value",
    [
        ("requested_shares", -1),
        ("requested_shares", 1.5),
        ("reference_price", float("inf")),
        ("reference_price", -1),
        ("quantity_unit", "lots"),
        ("currency", "USD"),
        ("price_convention", "unaffected"),
        ("decision_ns", 1),
        ("available_ns", 9),
        ("arrival_available_ns", 2),
        ("liquidity_quantity_unit", "lots"),
        ("market_volume_shares", -1),
        ("market_amount_cny", float("inf")),
        ("liquidity_end_ns", 9),
        ("opportunity_ns", 8),
        ("available_ns", 15),
        ("brokerage_terms_version", ""),
        ("evidence_kind", "unverified"),
    ],
)
def test_invalid_parent_semantics_rejected(column, value):
    with pytest.raises(ValueError):
        audit(parents(**{column: value}))


@pytest.mark.parametrize(
    "column,value",
    [
        ("shares", -1),
        ("shares", 0),
        ("shares", 0.5),
        ("shares", 101),
        ("price", float("nan")),
        ("price", -1),
        ("receipt_ns", 5),
        ("receipt_ns", 21),
        ("fill_ns", 11),
        ("fill_ns", 3),
        ("quantity_unit", "lots"),
        ("source_binding", "other"),
        ("evidence_kind", "broker_fills"),
        ("recorded_commission", -1),
        ("recorded_tax", float("inf")),
        ("child_id", ""),
    ],
)
def test_invalid_fill_semantics_rejected(column, value):
    with pytest.raises(ValueError):
        audit(f=fills(**{column: value}))


def test_conflicting_duplicate_or_cross_parent_child_is_rejected():
    with pytest.raises(ValueError, match="physical fill"):
        audit(f=pd.concat([fills(), fills(price=10.3)]))
    second = parents(parent_id="p2")
    with pytest.raises(ValueError, match="child"):
        audit(
            pd.concat([parents(), second]),
            pd.concat([fills(), fills(fill_id="f2", parent_id="p2")]),
        )


@pytest.mark.parametrize(
    "terms",
    [
        {"billing": "guess"},
        {"commission_bps": -1},
        {"minimum_commission": float("nan")},
        {"sell_tax_bps": float("inf")},
    ],
)
def test_invalid_brokerage_terms_rejected(terms):
    with pytest.raises(ValueError):
        audit(**terms)


def test_synthetic_adapter_reuses_scope_fit_and_later_validation_without_promotion():
    frames = []
    for i, shares in enumerate([10, 40, 90, 10, 40, 90]):
        report = audit(
            parents(
                available_ns=20 + i,
                completed_ns=10 + i,
                liquidity_end_ns=10 + i,
                liquidity_available_ns=17,
            ),
            fills(shares=shares),
        )
        frames.append(report.cost_observations(fee_basis="modeled"))
    observations = pd.concat(frames, ignore_index=True)
    model = fit_cost_scope(
        observations, cutoff_ns=22, source_binding="s", evidence_kind="synthetic"
    )
    result = validate_cost_scope(model, observations, source_binding="s")
    assert model.observations == 3
    assert result["observations"] == 3
    assert result["promoted"] is False
    assert result["evidence_kind"] == "synthetic"
    assert audit().cost_observations(fee_basis="recorded").empty
    asserted = audit(parents(evidence_kind="broker_fills"), fills(evidence_kind="broker_fills"))
    assert asserted.real_calibration == "unavailable"
    assert asserted.provenance_status == "caller_asserted"
    assert audit().source_digest != audit(f=fills(price=10.3)).source_digest


def test_clustered_uncertainty_uses_independent_clusters_not_fill_count():
    api = importlib.import_module("quant_backtest_core.evidence.cost_scope")
    assert hasattr(api, "validate_cost_scope_uncertainty"), "clustered uncertainty API is missing"
    obs = pd.DataFrame(
        [
            {
                "available_ns": i,
                "completed_ns": i,
                "participation": p,
                "filled_notional": 100.0,
                "shortfall_bps": 2 + 10 * p**0.5,
                "side": "buy",
                "liquidity_bucket": "liquid",
                "execution_minutes": 30,
                "date_cluster": "one",
            }
            for i, p in enumerate([0.01, 0.04, 0.09] * 3, 1)
        ]
    )
    model = fit_cost_scope(obs, cutoff_ns=3, source_binding="s", evidence_kind="synthetic")
    obs.loc[obs.available_ns > 3, "shortfall_bps"] += 1
    report = api.validate_cost_scope_uncertainty(
        model,
        obs,
        source_binding="s",
        cluster_column="date_cluster",
        cluster_kind="date",
        bootstrap_samples=200,
        seed=7,
    )
    assert report["independent_clusters"] == 1
    assert report["uncertainty_status"] == "insufficient_clusters"
    assert report["bias_interval_bps"] is None
    obs.loc[3:, "date_cluster"] = ["a", "a", "b", "b", "c", "c"]
    report = api.validate_cost_scope_uncertainty(
        model,
        obs,
        source_binding="s",
        cluster_column="date_cluster",
        cluster_kind="date",
        bootstrap_samples=200,
        seed=7,
    )
    assert report["independent_clusters"] == 3
    assert report["uncertainty_status"] == "evaluated"
    assert report["bias_interval_bps"] == pytest.approx([1, 1])
    assert report["rmse_interval_bps"] == pytest.approx([1, 1])
    assert report["real_calibration"] == "unavailable"
    assert report["promoted"] is False
    repeat = api.validate_cost_scope_uncertainty(
        model,
        obs,
        source_binding="s",
        cluster_column="date_cluster",
        cluster_kind="date",
        bootstrap_samples=200,
        seed=7,
    )
    assert report == repeat
    obs.loc[8, "side"] = "sell"
    assert (
        api.validate_cost_scope_uncertainty(
            model,
            obs,
            source_binding="s",
            cluster_column="date_cluster",
            cluster_kind="date",
            bootstrap_samples=200,
            seed=7,
        )["unsupported"]
        == 1
    )


def test_cluster_uncertainty_missing_and_invalid_clusters_do_not_certify_evidence():
    api = importlib.import_module("quant_backtest_core.evidence.cost_scope")
    assert hasattr(api, "validate_cost_scope_uncertainty"), "clustered uncertainty API is missing"
    obs = pd.DataFrame(
        [
            {
                "available_ns": i,
                "completed_ns": i,
                "participation": p,
                "filled_notional": 100.0,
                "shortfall_bps": 1.0,
                "side": "buy",
                "liquidity_bucket": "liquid",
                "execution_minutes": 30,
            }
            for i, p in enumerate([0.01, 0.04, 0.09] * 2, 1)
        ]
    )
    model = fit_cost_scope(obs, cutoff_ns=3, source_binding="s", evidence_kind="broker_fills")
    result = api.validate_cost_scope_uncertainty(
        model, obs, source_binding="s", cluster_column="day", cluster_kind="date"
    )
    assert result["uncertainty_status"] == "unavailable_clusters"
    assert result["real_calibration"] == "unavailable"
    with pytest.raises(ValueError):
        api.validate_cost_scope_uncertainty(
            model, obs, source_binding="s", cluster_column="day", cluster_kind="fill"
        )


def test_mixed_optional_rows_keep_missing_evidence_and_decimal_prices_adapt():
    from decimal import Decimal

    p = pd.concat(
        [parents(reference_price=Decimal("10")), parents(parent_id="p2")], ignore_index=True
    )
    f = pd.concat(
        [
            fills(recorded_commission=1, recorded_tax=0),
            fills(fill_id="f2", parent_id="p2", child_id="c2"),
        ],
        ignore_index=True,
    )
    report = audit(p, f)
    assert report.parents.iloc[1].recorded_cash_fees is None
    recorded = report.cost_observations(fee_basis="recorded")
    assert len(recorded) == 1
    assert recorded.iloc[0].shortfall_bps == pytest.approx(225)


def test_identical_physical_fill_numeric_representations_deduplicate():
    # A receipt serialized as float still represents the same physical price.
    from decimal import Decimal

    reports = pd.concat([fills(price=10, shares=40), fills(price=Decimal("10.00"), shares=40.0)])
    report = audit(f=reports)
    assert len(report.fills) == 1
    assert report.parents.iloc[0].filled_shares == 40


def test_cluster_bootstrap_does_not_treat_repeated_rows_as_independent_dates():
    api = importlib.import_module("quant_backtest_core.evidence.cost_scope")
    obs = pd.DataFrame(
        [
            {
                "available_ns": i,
                "completed_ns": i,
                "participation": p,
                "filled_notional": 100.0,
                "shortfall_bps": 0.0,
                "side": "buy",
                "liquidity_bucket": "liquid",
                "execution_minutes": 30,
                "day": "fit",
            }
            for i, p in enumerate([0.01, 0.04, 0.09], 1)
        ]
    )
    model = fit_cost_scope(obs, cutoff_ns=3, source_binding="s", evidence_kind="synthetic")
    later = pd.concat(
        [obs.iloc[[0]].assign(available_ns=4, completed_ns=4, day="a")] * 100
        + [
            obs.iloc[[0]].assign(available_ns=5, completed_ns=5, day="b", shortfall_bps=10),
            obs.iloc[[0]].assign(available_ns=6, completed_ns=6, day="c", shortfall_bps=20),
        ],
        ignore_index=True,
    )
    report = api.validate_cost_scope_uncertainty(
        model,
        later,
        source_binding="s",
        cluster_column="day",
        cluster_kind="date",
        bootstrap_samples=1000,
        seed=7,
    )
    assert report["observations"] == 102
    assert report["independent_clusters"] == 3
    assert report["bias_interval_bps"] == pytest.approx([0, 20])
    assert report["rmse_interval_bps"] == pytest.approx([0, 20])


def test_missing_quote_preserves_known_arrival_and_terminal_horizon_clocks():
    report = audit(parents(arrival_price=None, opportunity_price=None))
    row = report.parents.iloc[0]
    assert row.arrival_ns == 4
    assert row.opportunity_ns == 15
    assert row.arrival_price_shortfall is None
    assert row.opportunity_shortfall is None
    assert row.reference_price_shortfall == pytest.approx(8)


@pytest.mark.parametrize(
    "labels,residuals,expected_clusters,expected_status,expected_interval",
    [
        (["same-date"] * 3, [1, 2, 3], 1, "insufficient_clusters", None),
        (["date-a", "date-b", "date-c"], [2, 2, 2], 3, "evaluated", [2, 2]),
    ],
)
def test_cluster_identity_cannot_collide_with_temporary_residuals(
    labels, residuals, expected_clusters, expected_status, expected_interval
):
    from quant_backtest_core.evidence.cost_scope import validate_cost_scope_uncertainty

    training = pd.DataFrame(
        [
            {
                "available_ns": i,
                "completed_ns": i,
                "participation": participation,
                "filled_notional": 100.0,
                "shortfall_bps": 0.0,
                "side": "buy",
                "liquidity_bucket": "liquid",
                "execution_minutes": 30,
            }
            for i, participation in enumerate([0.01, 0.04, 0.09], 1)
        ]
    )
    model = fit_cost_scope(training, cutoff_ns=3, source_binding="s", evidence_kind="synthetic")
    later = training.assign(
        available_ns=[4, 5, 6],
        completed_ns=[4, 5, 6],
        shortfall_bps=residuals,
        date_cluster=labels,
        _error=labels,
    )
    # Positional residual alignment must also survive duplicate, unsorted index labels.
    later.index = [4, 4, 1]
    before = later.copy(deep=True)
    for column in ("date_cluster", "_error"):
        report = validate_cost_scope_uncertainty(
            model,
            later,
            source_binding="s",
            cluster_column=column,
            cluster_kind="date",
            bootstrap_samples=100,
            seed=7,
        )
        assert report["observations"] == 3
        assert report["independent_clusters"] == expected_clusters
        assert report["uncertainty_status"] == expected_status
        if expected_interval is None:
            assert report["bias_interval_bps"] is None
            assert report["rmse_interval_bps"] is None
        else:
            assert report["bias_interval_bps"] == pytest.approx(expected_interval)
            assert report["rmse_interval_bps"] == pytest.approx(expected_interval)
        assert_frame_equal(later, before)
