"""Execution seam keeps optimizer policy and full request with the caller."""

from dataclasses import replace

import pandas as pd
import pytest
from pending_fixtures import LiteralOptimizer, factor_request
from test_pending_allocation import observation, order

from quant_backtest_core.planning.pending_allocation import (
    pending_allocation_envelope,
    solve_pending_allocation,
)
from quant_backtest_core.planning.pending_protocol import (
    PendingOptimizer,
    PendingRequest,
    PendingSolveResult,
)


def test_protocol_exports_and_unchanged_request_actual_result_identity():
    assert PendingOptimizer and PendingRequest and PendingSolveResult
    r = factor_request(factor_bounds={"beta": (-0.5, 0.5)})
    state = observation(
        r, [order(r, "buy", "a", 10, 1), order(r, "sell", "a", -10, 2)], cash_before_reserves=123
    )
    optimizer = LiteralOptimizer(r)
    result = solve_pending_allocation(optimizer, r, state, net_band=(-0.2, 0.2))
    assert result.base_result is optimizer.result
    request, envelope, cash_limit = optimizer.calls[0]
    assert request is r and envelope is result.envelope
    assert envelope.gross_limit == pytest.approx(0.8)
    assert envelope.lower_bounds.tolist() == pytest.approx([-0.4, -0.5, -0.5])
    assert envelope.upper_bounds.tolist() == pytest.approx([0.4, 0.5, 0.5])
    assert envelope.factor_bounds == {"beta": (-0.3, 0.3)}
    assert cash_limit[0] == pytest.approx(0.02)
    assert cash_limit[1].tolist() == [0, 0, 0]
    assert r.gross_limit == 1 and r.lower_bounds.tolist() == [-0.5] * 3
    assert result.paper_only is True and result.executable is False


def test_full_caller_validation_precedes_even_infeasible_envelope():
    r = factor_request()

    class InvalidResearchPolicy(LiteralOptimizer):
        def validate(self, request):
            assert request is r
            raise ValueError("caller-owned risk validation")

    optimizer = InvalidResearchPolicy(r)
    with pytest.raises(ValueError, match="caller-owned risk"):
        solve_pending_allocation(
            optimizer, r, observation(r, cash_before_reserves=-1), net_band=(-1, 1)
        )
    assert optimizer.calls == []


@pytest.mark.parametrize("status", ["infeasible", "numerical_failure"])
def test_solver_failure_never_releases_targets(status):
    r = factor_request()
    result = solve_pending_allocation(
        LiteralOptimizer(r, status=status), r, observation(r), net_band=(-1, 1)
    )
    assert result.status == status
    assert result.base_result is result.new_trade_weights is None


@pytest.mark.parametrize("excess, expected", [(0.5e-7, "optimal"), (2e-7, "numerical_failure")])
def test_literal_residual_rejects_above_existing_tolerance(excess, expected):
    r = factor_request()
    optimizer = LiteralOptimizer(r, (0.5 + excess, -0.5, 0))
    result = solve_pending_allocation(optimizer, r, observation(r), net_band=(-1, 1))
    assert result.status == expected
    if expected == "numerical_failure":
        assert result.base_result is result.new_trade_weights is None
        assert "1e-7" in result.message


@pytest.mark.parametrize(
    "field, value",
    [
        ("gross_limit", float("nan")),
        ("gross_limit", -1),
        ("net_target", float("inf")),
        ("factor_bounds", {"missing": (-1, 1)}),
        ("factor_bounds", {"beta": (1, -1)}),
        ("decision_time", pd.Timestamp("2025-01-01", tz="UTC")),
        ("information_time", pd.Timestamp("2026-01-01")),
        ("expected_returns", pd.Series([1, 2], index=["a", "b"])),
        ("lower_bounds", pd.Series([1, 1, 1], index=["a", "b", "c"])),
    ],
)
def test_neutral_envelope_validates_execution_fields(field, value):
    r = replace(factor_request(), **{field: value})
    with pytest.raises(ValueError):
        pending_allocation_envelope(r, observation(r), net_band=(-1, 1))
