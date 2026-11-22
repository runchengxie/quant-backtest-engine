"""Current marks certify actual live exposure, never future targets or stale NAV."""

import numpy as np
import pandas as pd
import pytest
from quant_backtest_engine.product import ClockSet

from quant_backtest_core.daily.contracts import (
    DailyInputLayout,
    DailyReplayRequest,
    ExecutionCalendar,
    utc_ns,
)
from quant_backtest_core.daily.execution_sim import ExecutionSimConfig
from quant_backtest_core.daily.runner import run_daily

DAYS = ("2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08")


def request(mode, *, prices=None, targets=None):
    targets = targets or [(DAYS[0], "A", 1.0)]
    positions = pd.DataFrame(
        [
            {"rebalance_date": day, "entry_date": day, "symbol": symbol, "weight": weight}
            for day, symbol, weight in targets
        ]
    )
    pricing = pd.DataFrame(
        [
            {
                "trade_date": day,
                "symbol": symbol,
                "close": (prices or {}).get((day, symbol), 10.0),
                "amount": 1_000_000.0,
            }
            for day in DAYS
            for symbol in ("A", "B")
        ]
    )

    def ns(day, hour):
        return utc_ns(pd.Timestamp(f"{day}T{hour}:00:00+08:00"))

    clocks = {
        day: ClockSet(
            None, ns(day, "08"), ns(day, "09"), ns(day, "10"), None, None, ns(DAYS[-1], "16")
        )
        for day in positions.rebalance_date
    }
    return DailyReplayRequest(
        positions,
        pricing,
        ExecutionCalendar.from_dates("Asia/Shanghai", DAYS),
        clocks,
        ExecutionSimConfig(
            enabled=True,
            portfolio_value=1000,
            participation_rate=1,
            liquidity_cols=("amount",),
            buy_max_days=1,
            sell_max_days=1,
        ),
        mode,
        "raw",
        (),
        layout=DailyInputLayout(
            "close",
            "close",
            None,
            None,
            None,
            "CNY",
            "raw_share",
            "CNY/raw_share",
            {"amount": "CNY"},
        ),
        decision_timing={},
    )


@pytest.mark.parametrize("mode", ["ideal", "adjusted", "sequenced"])
def test_future_unheld_quote_gaps_and_post_exit_gaps_do_not_invalidate(mode):
    prices = {(day, "B"): np.nan for day in DAYS[:2]}
    prices.update({(day, "A"): np.nan for day in DAYS[3:]})
    result = run_daily(request(mode, prices=prices, targets=[(DAYS[0], "A", 1), (DAYS[2], "B", 1)]))
    assert result.summary["execution_summary"]["valuation_complete"]
    assert result.summary["execution_summary"]["daily_return"] == (0.0,) * 5
    assert result.valuation_marks.endpoint_complete.tolist() == [True] * 5
    assert result.valuation_marks.held_symbols.tolist() == [("A",), ("A",), ("B",), ("B",), ("B",)]


@pytest.mark.parametrize("mode", ["ideal", "adjusted", "sequenced"])
@pytest.mark.parametrize("bad", [np.nan, np.inf, 0.0, -1.0])
def test_held_missing_current_mark_keeps_carried_nav_but_invalidates_two_intervals(mode, bad):
    result = run_daily(request(mode, prices={(DAYS[1], "A"): bad}))
    assert result.daily.portfolio_value.tolist() == [1000.0] * 5
    assert result.summary["execution_summary"]["daily_return"] == (0.0, None, None, 0.0, 0.0)
    assert not result.summary["execution_summary"]["valuation_complete"]
    assert result.summary["execution_summary"]["cumulative_return"] is None
    assert result.valuation_marks.endpoint_complete.tolist() == [True, False, True, True, True]
    row = result.valuation_marks.iloc[1]
    assert row.missing_symbols == ("A",)
    assert row.reason == "missing_current_price"
    assert row.required_marks == 1 and row.current_marks == 0


@pytest.mark.parametrize("mode", ["ideal", "adjusted", "sequenced"])
def test_zero_weight_cash_target_and_post_exit_missing_quotes_are_complete(mode):
    targets = [(DAYS[0], "A", 1), (DAYS[1], "B", 0)]
    prices = {(day, symbol): np.nan for day in DAYS[2:] for symbol in ("A", "B")}
    result = run_daily(request(mode, prices=prices, targets=targets))
    assert result.summary["execution_summary"]["valuation_complete"]
    assert result.valuation_marks.iloc[-1].held_symbols == ()
    assert result.valuation_marks.iloc[-1].reason == "cash_only"
    assert result.daily.cash.iloc[-1] == 1000


@pytest.mark.parametrize("mode", ["ideal", "adjusted", "sequenced"])
def test_missing_entire_held_quote_row_and_recovery_keeps_original_returns(mode):
    from dataclasses import replace

    req = request(mode, prices={(DAYS[2], "A"): 11, (DAYS[3], "A"): 12, (DAYS[4], "A"): 12})
    pricing = req.pricing.loc[~(req.pricing.trade_date.eq(DAYS[1]) & req.pricing.symbol.eq("A"))]
    result = run_daily(replace(req, pricing=pricing))
    assert result.daily.executed_return.tolist() == pytest.approx([0, 0, 0.1, 12 / 11 - 1, 0])
    assert result.summary["execution_summary"]["daily_return"] == pytest.approx(
        (0, None, None, 12 / 11 - 1, 0), nan_ok=True
    )


@pytest.mark.parametrize("mode", ["ideal", "adjusted", "sequenced"])
def test_cash_only_start_does_not_require_any_target_quote(mode):
    result = run_daily(
        request(mode, targets=[(DAYS[0], "A", 0)], prices={(day, "A"): np.nan for day in DAYS})
    )
    assert result.summary["execution_summary"]["valuation_complete"]
    assert result.valuation_marks.reason.tolist() == ["cash_only"] * 5


@pytest.mark.parametrize("mode", ["adjusted", "sequenced"])
def test_cash_rights_after_sale_need_finite_amount_not_unheld_stock_mark(mode):
    from dataclasses import replace

    from quant_backtest_core.daily.execution_sim import CorporateAction

    event = CorporateAction(
        event_id="cash",
        symbol="A",
        available_date="20200101",
        record_date=DAYS[0],
        ex_date=DAYS[1],
        cash_per_share=1,
        cash_pay_date=DAYS[4],
    )
    req = request(
        mode,
        targets=[(DAYS[0], "A", 1), (DAYS[1], "B", 0)],
        prices={(day, "A"): np.nan if day in DAYS[2:] else 9 for day in DAYS[1:]},
    )
    result = run_daily(replace(req, corporate_actions=(event,)))
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000] * 5)
    assert result.daily.cash_receivable.tolist() == [0, 100, 100, 100, 0]
    assert result.valuation_marks.endpoint_complete.all()
    assert result.valuation_marks.reason.tolist()[1:4] == ["cash_and_receivables"] * 3


@pytest.mark.parametrize("mode", ["adjusted", "sequenced"])
def test_stock_rights_require_current_price_after_original_position_exited(mode):
    from dataclasses import replace

    from quant_backtest_core.daily.execution_sim import CorporateAction

    event = CorporateAction(
        event_id="stock",
        symbol="A",
        available_date="20200101",
        record_date=DAYS[0],
        ex_date=DAYS[1],
        stock_per_share=1,
        stock_tradable_date=DAYS[4],
    )
    req = request(
        mode,
        targets=[(DAYS[0], "A", 1), (DAYS[1], "B", 0)],
        prices={(day, "A"): 5 for day in DAYS[1:]},
    )
    result = run_daily(replace(req, corporate_actions=(event,)))
    middle = result.valuation_marks.iloc[2]
    assert middle.held_symbols == ()
    assert middle.stock_receivable_symbols == ("A",)
    assert middle.required_marks == 1 and middle.endpoint_complete
    missing = req.pricing.copy()
    missing.loc[missing.trade_date.eq(DAYS[2]) & missing.symbol.eq("A"), "close"] = np.nan
    with pytest.raises(ValueError, match="raw mark"):
        run_daily(replace(req, corporate_actions=(event,), pricing=missing))


def test_legacy_result_default_and_absent_evidence_fail_closed(monkeypatch):
    from dataclasses import replace

    from quant_backtest_core.daily.execution_sim import ExecutionAdjustedNavResult

    owned = run_daily(request("ideal"))
    legacy = ExecutionAdjustedNavResult(owned.summary, owned.daily, owned.orders, owned.fills)
    assert legacy.valuation_marks is None
    monkeypatch.setattr(
        "quant_backtest_core.daily.runner.simulate_ideal_daily_nav", lambda *a, **k: legacy
    )
    result = run_daily(request("ideal"))
    assert result.summary["execution_summary"]["daily_return"] == (None,) * 5
    assert not result.summary["execution_summary"]["valuation_complete"]
    misaligned = replace(owned, valuation_marks=owned.valuation_marks.iloc[::-1])
    monkeypatch.setattr(
        "quant_backtest_core.daily.runner.simulate_ideal_daily_nav", lambda *a, **k: misaligned
    )
    with pytest.raises(ValueError, match="align"):
        run_daily(request("ideal"))


@pytest.mark.parametrize("bad_field", ["cash", "cash_receivable", "stock_receivable_value"])
def test_endpoint_evidence_rejects_unknown_cash_and_receivables(bad_field):
    from quant_backtest_core.daily.execution_sim.valuation import endpoint_marks

    kwargs = {"cash": 1000.0, "cash_receivable": 10.0, "stock_receivable_value": 0.0}
    kwargs[bad_field] = np.nan
    row = endpoint_marks(day=pd.Timestamp(DAYS[0]), shares={}, price_table=pd.DataFrame(), **kwargs)
    assert not row["endpoint_complete"]
    assert "nonfinite" in row["reason"]


@pytest.mark.parametrize("field", ["shares", "stock_receivables"])
@pytest.mark.parametrize("quantity", [-1.0, np.nan, np.inf])
def test_invalid_live_share_or_stock_right_quantity_cannot_certify(field, quantity):
    from quant_backtest_core.daily.execution_sim.valuation import endpoint_marks

    kwargs = {"shares": {}, "stock_receivables": {}}
    kwargs[field] = {"A": quantity}
    prices = pd.DataFrame({"A": [10.0]}, index=[pd.Timestamp(DAYS[0])])
    row = endpoint_marks(day=pd.Timestamp(DAYS[0]), cash=1000, price_table=prices, **kwargs)
    assert not row["endpoint_complete"]
    assert row["reason"] == "invalid_position_quantity"
