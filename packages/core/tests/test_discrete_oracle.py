# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_impact_optimization_scenarios.py
import pytest

from quant_backtest_core.planning.discrete_oracle import enumerate_lot_portfolios


def test_discrete_oracle_exposes_rounding_gap_and_budget():
    result = enumerate_lot_portfolios(
        prices=[6, 4],
        target_quantities=[1.5, 1.5],
        max_lots=[3, 3],
        lot_sizes=[1, 1],
        cash_budget=14,
        minimum_commission=1,
        candidate_quantities=[2, 1],
    )
    assert result.status == "optimal_exhaustive"
    assert result.quantities == (1, 1)
    assert result.spent == 12
    assert result.objective == 0.5
    assert result.candidate_status == "infeasible"
    assert result.candidate_gap is None
    assert result.evaluated == 16


def test_feasible_heuristic_has_reported_suboptimal_gap():
    result = enumerate_lot_portfolios(
        prices=[6, 4],
        target_quantities=[1.5, 1.5],
        max_lots=[3, 3],
        lot_sizes=[1, 1],
        cash_budget=14,
        minimum_commission=1,
        candidate_quantities=[0, 2],
    )
    assert result.candidate_status == "feasible"
    assert result.candidate_gap == 2


def test_search_limit_is_rejection_not_false_optimality():
    result = enumerate_lot_portfolios(
        prices=[1],
        target_quantities=[1],
        max_lots=[100],
        lot_sizes=[1],
        cash_budget=10,
        max_states=10,
    )
    assert result.status == "search_limit"
    assert result.quantities is None
    assert result.evaluated == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_lots": [-1]},
        {"lot_sizes": [0]},
        {"cash_budget": -1},
        {"max_states": 0},
        {"minimum_commission": float("inf")},
    ],
)
def test_lot_oracle_rejects_invalid_contract(kwargs):
    base = {
        "prices": [1],
        "target_quantities": [1],
        "max_lots": [2],
        "lot_sizes": [1],
        "cash_budget": 3,
    }
    with pytest.raises(ValueError):
        enumerate_lot_portfolios(**(base | kwargs))


def test_decimal_cash_boundary_preserves_feasible_exact_target():
    result = enumerate_lot_portfolios(
        prices=[0.1, 0.2],
        target_quantities=[1, 1],
        max_lots=[1, 1],
        lot_sizes=[1, 1],
        cash_budget=0.3,
    )
    assert result.quantities == (1, 1)
    assert result.spent == 0.3
    assert result.objective == 0
