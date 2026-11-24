"""Synthetic opt-in stale valuation evidence never changes executable prices."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from test_held_position_marks import DAYS, request

from quant_backtest_core.daily.execution_sim import (
    ExecutionSimConfig,
    build_execution_sim_config,
    describe_execution_sim_config,
    simulate_capacity_execution,
    simulate_execution_adjusted_nav,
)
from quant_backtest_core.daily.execution_sim.valuation import endpoint_marks
from quant_backtest_core.daily.runner import run_daily


def policy(**changes):
    return dict(
        valuation_policy="suspended_last_quote",
        valuation_suspension_col="suspended",
        valuation_max_stale_sessions=2,
        **changes,
    )


def replay(*, mode="adjusted", flags=True, missing=(1,), max_age=2, targets=None):
    req = request(mode, prices={(DAYS[i], "A"): np.nan for i in missing}, targets=targets)
    prices = req.pricing.assign(suspended=flags)
    return replace(
        req,
        pricing=prices,
        price_basis="adjusted",
        config=replace(req.config, **(policy() | {"valuation_max_stale_sessions": max_age})),
        layout=replace(req.layout, quantity_unit="adjusted_share", price_unit="CNY/adjusted_share"),
    )


@pytest.mark.parametrize("mode", ["adjusted", "sequenced"])
def test_carry_and_resumption_keep_current_evidence_and_no_fills(mode):
    req = replay(mode=mode)
    req.pricing.loc[req.pricing.trade_date.eq(DAYS[2]) & req.pricing.symbol.eq("A"), "close"] = 12
    original = req.pricing.copy(deep=True)
    result = run_daily(req)
    row = result.valuation_marks.iloc[1]
    assert row.endpoint_complete and row.current_marks == 0
    assert row.missing_symbols == ("A",) and row.policy_valued_symbols == ("A",)
    assert row.policy_quote_dates == (DAYS[0],)
    assert row.policy_quote_ages == (1,)
    assert row.unresolved_symbols == ()
    assert result.valuation_marks.iloc[2].policy_valued_symbols == ()
    assert result.daily.portfolio_value.tolist() == [1000, 1000, 1200, 1000, 1000]
    assert result.summary["execution_summary"]["valuation_complete"]
    assert result.fills.trade_date.tolist() == [DAYS[0].replace("-", "")]
    pd.testing.assert_frame_equal(req.pricing, original)


@pytest.mark.parametrize("flag", [False, None, np.nan, "true", 1])
def test_missing_or_nonboolean_suspension_cannot_certify(flag):
    result = run_daily(replay(flags=flag))
    assert not result.valuation_marks.iloc[1].endpoint_complete
    assert result.valuation_marks.iloc[1].unresolved_symbols == ("A",)


def test_global_session_age_cap_and_current_quote_reset():
    result = run_daily(replay(missing=(1, 2, 3), max_age=2))
    assert result.valuation_marks.endpoint_complete.tolist() == [True, True, True, False, True]
    assert result.valuation_marks.iloc[2].policy_quote_ages == (2,)
    assert result.valuation_marks.iloc[3].unresolved_symbols == ("A",)


@pytest.mark.parametrize("last", [None, {}, {"A": 0}, {"A": np.inf}, {"A": 99}])
def test_actual_prior_quote_without_matching_live_owner_price_is_not_evidence(last):
    prices = pd.DataFrame({"A": [10, np.nan, 99]}, index=pd.to_datetime(DAYS[:3]))
    row = endpoint_marks(
        day=pd.Timestamp(DAYS[1]),
        shares={"A": 1},
        cash=0,
        price_table=prices,
        config=ExecutionSimConfig(**policy()),
        last_prices=last,
        suspension_table=pd.DataFrame({"A": [True]}, index=pd.to_datetime([DAYS[1]])),
        trade_dates=list(pd.to_datetime(DAYS)),
    )
    assert not row["endpoint_complete"]


def test_default_matches_explicit_default_and_retains_incomplete_returns():
    req = request("adjusted", prices={(DAYS[1], "A"): np.nan})
    a = run_daily(req)
    b = run_daily(replace(req, config=replace(req.config, valuation_policy="current_mark_only")))
    pd.testing.assert_frame_equal(a.daily, b.daily)
    pd.testing.assert_frame_equal(a.valuation_marks, b.valuation_marks)
    assert a.summary == b.summary
    assert not a.summary["execution_summary"]["valuation_complete"]


@pytest.mark.parametrize(
    "changes",
    [
        {"valuation_policy": "guess"},
        {"valuation_suspension_col": None},
        {"valuation_suspension_col": " "},
        {"valuation_max_stale_sessions": None},
        {"valuation_max_stale_sessions": 0},
        {"valuation_max_stale_sessions": True},
        {"valuation_max_stale_sessions": 1.5},
    ],
)
def test_config_rejects_invalid_policy(changes):
    with pytest.raises(ValueError):
        ExecutionSimConfig(**(policy() | changes))


def test_config_mapping_description_and_missing_selector():
    cfg = build_execution_sim_config({"enabled": True, **policy()})
    assert all(describe_execution_sim_config(cfg)[k] == v for k, v in policy().items())
    req = replay()
    with pytest.raises(ValueError, match="suspended"):
        run_daily(replace(req, pricing=req.pricing.drop(columns="suspended")))


@pytest.mark.parametrize("mode", ["ideal", "capacity"])
def test_nonledger_modes_reject_opt_in(mode):
    with pytest.raises(ValueError, match="valuation"):
        run_daily(replay(mode=mode))


def test_raw_and_direct_capacity_reject_opt_in():
    req = replay()
    with pytest.raises(ValueError, match="adjusted"):
        simulate_execution_adjusted_nav(
            req.positions, req.pricing, req.config, price_col="close", price_basis="raw"
        )
    with pytest.raises(ValueError, match="valuation"):
        simulate_capacity_execution(req.positions, req.pricing, req.config, price_col="close")


def test_missing_suspended_quote_delays_sell_without_creating_cash_or_waiving_costs():
    req = replay(targets=[(DAYS[0], "A", 1), (DAYS[1], "B", 1)])
    req = replace(req, config=replace(req.config, sell_max_days=3))
    result = simulate_execution_adjusted_nav(
        req.positions,
        req.pricing,
        req.config,
        price_col="close",
        price_basis="adjusted",
        transaction_cost_bps=10,
    )
    assert not result.fills.trade_date.eq(DAYS[1].replace("-", "")).any()
    assert result.fills.side.tolist() == ["buy", "sell"]
    assert result.fills.trade_date.tolist() == [DAYS[0].replace("-", ""), DAYS[2].replace("-", "")]
    assert result.daily.transaction_cost.sum() > 0
    assert result.daily.portfolio_value.iloc[-1] == pytest.approx(
        1000 - result.daily.transaction_cost.sum()
    )
    assert result.daily.portfolio_value.tolist() == pytest.approx(
        (result.daily.cash + result.daily.invested_value).tolist()
    )
    assert result.valuation_marks.iloc[1].held_symbols == ("A",)
    assert result.valuation_marks.iloc[1].endpoint_complete


def test_only_future_quote_or_missing_current_row_does_not_invent_prior_mark():
    prices = pd.DataFrame({"A": [np.nan, np.nan, 10]}, index=pd.to_datetime(DAYS[:3]))
    kwargs = dict(
        day=pd.Timestamp(DAYS[1]),
        shares={"A": 1},
        cash=0,
        price_table=prices,
        config=ExecutionSimConfig(**policy()),
        last_prices={"A": 10},
        suspension_table=pd.DataFrame({"A": [True]}, index=pd.to_datetime([DAYS[1]])),
        trade_dates=list(pd.to_datetime(DAYS)),
    )
    assert not endpoint_marks(**kwargs)["endpoint_complete"]
    req = replay()
    req = replace(
        req,
        pricing=req.pricing.loc[~(req.pricing.trade_date.eq(DAYS[1]) & req.pricing.symbol.eq("A"))],
    )
    assert not run_daily(req).valuation_marks.iloc[1].endpoint_complete


def test_current_quote_wins_even_without_suspension_and_source_does_not_look_ahead():
    result = run_daily(replay(flags=None, missing=()))
    assert result.valuation_marks.endpoint_complete.all()
    assert result.valuation_marks.current_marks.tolist() == [1] * len(DAYS)
    req = replay(missing=(1, 2))
    later = req.pricing.copy()
    later.loc[later.trade_date.eq(DAYS[4]), "close"] = 999
    a, b = run_daily(req), run_daily(replace(req, pricing=later))
    pd.testing.assert_frame_equal(a.valuation_marks.iloc[:4], b.valuation_marks.iloc[:4])
    pd.testing.assert_frame_equal(a.daily.iloc[:4], b.daily.iloc[:4])


def test_direct_and_prepared_api_reject_absent_or_reused_suspension_selector():
    from quant_backtest_core.daily.execution_sim import prepare_execution_tables

    req = replay()
    base = replace(req.config, valuation_policy="current_mark_only")
    prepared = prepare_execution_tables(req.pricing, base, price_col="close")
    with pytest.raises(ValueError, match="suspension"):
        simulate_execution_adjusted_nav(
            req.positions,
            req.pricing,
            req.config,
            price_col="close",
            price_basis="adjusted",
            prepared_tables=prepared,
        )
    with pytest.raises(ValueError, match="separate"):
        simulate_execution_adjusted_nav(
            req.positions,
            req.pricing,
            req.config,
            price_col="close",
            price_basis="adjusted",
            sell_tradable_col="suspended",
        )


def test_explicit_corporate_action_opt_in_is_rejected_before_ledger():
    from quant_backtest_core.daily.execution_sim import CorporateAction

    req = replay()
    action = CorporateAction(
        "split", "A", DAYS[0], DAYS[0], DAYS[1], stock_per_share=1, stock_tradable_date=DAYS[2]
    )
    with pytest.raises(ValueError, match="corporate actions"):
        simulate_execution_adjusted_nav(
            req.positions,
            req.pricing,
            req.config,
            price_col="close",
            price_basis="adjusted",
            corporate_actions=(action,),
        )


def test_prepared_suspension_evidence_must_match_declared_selector():
    from quant_backtest_core.daily.execution_sim import prepare_execution_tables

    req = replay()
    prices = req.pricing.assign(other_suspension=False)
    prepared = prepare_execution_tables(prices, req.config, price_col="close")
    changed = replace(req.config, valuation_suspension_col="other_suspension")
    with pytest.raises(ValueError, match="suspension"):
        simulate_execution_adjusted_nav(
            req.positions,
            prices,
            changed,
            price_col="close",
            price_basis="adjusted",
            prepared_tables=prepared,
        )


@pytest.mark.parametrize("opt_in", [False, True])
def test_empty_and_nonempty_policy_metadata_parquet_round_trip(opt_in):
    from io import BytesIO

    pytest.importorskip("pyarrow")
    result = run_daily(replay() if opt_in else request("adjusted"))
    original = result.valuation_marks
    stream = BytesIO()
    original.to_parquet(stream, index=False)
    stream.seek(0)
    restored = pd.read_parquet(stream)
    assert restored.valuation_policy.tolist() == original.valuation_policy.tolist()
    assert restored.endpoint_complete.tolist() == original.endpoint_complete.tolist()
    for name in (
        "policy_valued_symbols",
        "policy_quote_dates",
        "policy_quote_ages",
        "unresolved_symbols",
    ):
        assert [tuple(value) for value in restored[name]] == original[name].tolist()


@pytest.mark.parametrize("bad_quote", [0, -1, np.inf, -np.inf])
def test_invalid_current_quotes_never_become_current_evidence(bad_quote):
    req = replay()
    req.pricing.loc[req.pricing.trade_date.eq(DAYS[1]) & req.pricing.symbol.eq("A"), "close"] = (
        bad_quote
    )
    row = run_daily(req).valuation_marks.iloc[1]
    assert row.endpoint_complete and row.current_marks == 0
    assert row.policy_valued_symbols == ("A",)
