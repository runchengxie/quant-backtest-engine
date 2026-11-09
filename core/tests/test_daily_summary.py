from dataclasses import asdict

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from quant_backtest_core.daily.contracts import DailySummaryEvidence
from quant_backtest_core.daily.summary import summarize_execution


def evidence(marks=(True, True), flows=(True, True), daily="available", fills="available"):
    return DailySummaryEvidence(daily, fills, marks, flows)


def frames():
    # Literal no-flow owner ledger: 100 -> 110 -> 99.
    return pd.DataFrame(
        {"nav": [110.0, 99.0], "executed_return": [0.1, -0.1], "transaction_cost": [100.0, 200.0]}
    ), pd.DataFrame(
        {
            "cost_commission": [1.0, 2.0],
            "cost_stamp_tax": [0.1, 0.2],
            "cost_transfer_fee": [0.01, 0.02],
        }
    )


def test_two_period_ledger_owner_returns_and_actual_fees_once():
    daily, fills = frames()
    d, f = daily.copy(deep=True), fills.copy(deep=True)
    result = summarize_execution(daily, fills, evidence=evidence())
    assert result.daily_return == (0.1, -0.1)
    assert result.cumulative_return == pytest.approx(-0.01)
    assert result.total_fees == pytest.approx(3.33)
    assert result.turnover is None
    assert result.valuation_complete
    assert set(asdict(result)) == {
        "daily_return",
        "cumulative_return",
        "turnover",
        "total_fees",
        "valuation_complete",
    }
    assert_frame_equal(daily, d)
    assert_frame_equal(fills, f)


@pytest.mark.parametrize(
    "marks,flows,complete",
    [
        ((True, False), (True, True), False),
        ((True, True), (True, False), True),
        ((True, True), (True, None), True),
    ],
)
def test_missing_marks_deposit_unknown_flow(marks, flows, complete):
    daily, fills = frames()
    daily["external_capital"] = [0, 50]
    result = summarize_execution(daily, fills, evidence=evidence(marks, flows))
    assert result.daily_return == (0.1, None)
    assert result.cumulative_return is None
    assert result.valuation_complete is complete


def test_missing_evidence_and_nonfinite_return():
    daily, fills = frames()
    assert summarize_execution(daily, fills).daily_return == (None, None)
    for value in (float("nan"), float("inf"), None):
        daily.loc[1, "executed_return"] = value
        assert summarize_execution(daily, fills, evidence=evidence()).cumulative_return is None


def test_supported_empty_differs_from_unavailable():
    d = pd.DataFrame()
    f = pd.DataFrame(columns=["cost_commission", "cost_stamp_tax", "cost_transfer_fee"])
    yes = summarize_execution(d, f, evidence=evidence((), ()))
    no = summarize_execution(d, f)
    assert (yes.daily_return, yes.cumulative_return, yes.valuation_complete, yes.total_fees) == (
        (),
        0.0,
        True,
        0.0,
    )
    assert (no.daily_return, no.cumulative_return, no.valuation_complete, no.total_fees) == (
        (),
        None,
        False,
        None,
    )


def test_fee_missing_column_or_component():
    daily, fills = frames()
    for col in fills:
        assert (
            summarize_execution(daily, fills.drop(columns=col), evidence=evidence()).total_fees
            is None
        )
        broken = fills.copy()
        broken.loc[0, col] = float("nan")
        assert summarize_execution(daily, broken, evidence=evidence()).total_fees is None


def test_alignment_and_status_contradictions():
    daily, fills = frames()
    with pytest.raises(ValueError):
        summarize_execution(daily, fills, evidence=evidence((True,), (True,)))
    with pytest.raises(ValueError):
        evidence(daily="unavailable")
    with pytest.raises(ValueError):
        summarize_execution(daily, fills, evidence=evidence(fills="unavailable"))
    with pytest.raises(ValueError):
        DailySummaryEvidence("available", "available", (1,), (True,))
