from dataclasses import replace

import pandas as pd
import pytest

from quant_backtest_core.daily.position_backtest import (
    PositionBacktestConfig,
    run_position_backtest,
)


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    positions = pd.DataFrame(
        [
            {"rebalance_date": "20240101", "entry_date": "20240102", "symbol": "A", "weight": 1.0},
            {"rebalance_date": "20240102", "entry_date": "20240103", "symbol": "A", "weight": 1.0},
        ]
    )
    prices = pd.DataFrame(
        [
            {"trade_date": "20240102", "symbol": "A", "open": 10.0, "close": 11.0},
            {"trade_date": "20240103", "symbol": "A", "open": 12.0, "close": 15.0},
            {"trade_date": "20240103", "symbol": "B", "open": 100.0, "close": 110.0},
        ]
    )
    periods = pd.DataFrame(
        [
            {"rebalance_date": "20240101", "entry_date": "20240102", "exit_date": "20240103"},
            {"rebalance_date": "20240102", "entry_date": "20240103", "exit_date": "20240103"},
        ]
    )
    return positions, prices, periods


def _config() -> PositionBacktestConfig:
    return PositionBacktestConfig(
        price_col="open",
        entry_price_col="open",
        exit_price_col="open",
        terminal_exit_price_col="close",
        preserve_gross_exposure=True,
        transaction_cost_bps=10.0,
    )


def test_terminal_close_and_same_day_open_handoff_preserve_continuous_wealth() -> None:
    positions, prices, periods = _inputs()
    original = prices.copy(deep=True)
    result = run_position_backtest(
        positions=positions, pricing=prices, periods=periods, config=_config()
    )
    assert result.periods["gross_return"].tolist() == pytest.approx([0.2, 0.25])
    assert (1 + result.gross_returns["gross_return"]).prod() == pytest.approx(15 / 10)
    assert result.periods["fee_cost"].tolist() == pytest.approx([0.001, 0.0])
    assert result.net_returns["period_end"].tolist() == ["2024-01-03", "2024-01-03"]
    pd.testing.assert_frame_equal(prices, original)


def test_terminal_replacement_keeps_prior_cost_state_instead_of_reinitializing() -> None:
    positions, prices, periods = _inputs()
    positions.loc[1, "symbol"] = "B"
    result = run_position_backtest(
        positions=positions, pricing=prices, periods=periods, config=_config()
    )
    assert result.periods["gross_return"].tolist() == pytest.approx([0.2, 0.1])
    assert result.periods["fee_cost"].tolist() == pytest.approx([0.001, 0.002])


def test_default_none_is_identical_to_historical_uniform_exit_behavior() -> None:
    positions, prices, periods = _inputs()
    ordinary = PositionBacktestConfig(price_col="open", transaction_cost_bps=10)
    baseline = run_position_backtest(
        positions=positions, pricing=prices, periods=periods, config=ordinary
    )
    explicit = run_position_backtest(
        positions=positions,
        pricing=prices,
        periods=periods,
        config=replace(ordinary, terminal_exit_price_col=None),
    )
    pd.testing.assert_frame_equal(baseline.periods, explicit.periods)
    assert baseline.summary == explicit.summary
    assert baseline.gross_returns["gross_return"].tolist() == pytest.approx([0.2, 0.0])


def test_terminal_close_is_only_for_last_requested_period_even_if_it_is_skipped() -> None:
    positions, prices, periods = _inputs()
    result = run_position_backtest(
        positions=positions.iloc[:1], pricing=prices, periods=periods, config=_config()
    )
    assert result.gross_returns["gross_return"].tolist() == pytest.approx([0.2])


def test_missing_unused_close_and_missing_terminal_open_do_not_drop_valid_marks() -> None:
    positions, prices, periods = _inputs()
    prices.loc[0, "close"] = float("nan")
    prices = pd.concat(
        [
            prices,
            pd.DataFrame(
                [{"trade_date": "20240104", "symbol": "A", "open": float("nan"), "close": 18.0}]
            ),
        ],
        ignore_index=True,
    )
    periods.loc[1, "exit_date"] = "20240104"
    result = run_position_backtest(
        positions=positions, pricing=prices, periods=periods, config=_config()
    )
    assert result.gross_returns["gross_return"].tolist() == pytest.approx([0.2, 0.5])


def test_missing_terminal_close_keeps_unavailable_weight_in_cash() -> None:
    positions, prices, periods = _inputs()
    positions.loc[1, "weight"] = 0.5
    positions = pd.concat([positions, positions.iloc[[1]].assign(symbol="B")], ignore_index=True)
    prices.loc[prices["symbol"].eq("A") & prices["trade_date"].eq("20240103"), "close"] = float(
        "nan"
    )
    result = run_position_backtest(
        positions=positions, pricing=prices, periods=periods, config=_config()
    )
    assert result.periods["gross_return"].tolist() == pytest.approx([0.2, 0.05])
    assert result.periods["cash_weight"].iloc[-1] == pytest.approx(0.5)
    assert result.periods["missing_price_count"].iloc[-1] == 1


def test_missing_terminal_column_fails_explicitly() -> None:
    positions, prices, periods = _inputs()
    with pytest.raises(ValueError, match="close"):
        run_position_backtest(
            positions=positions,
            pricing=prices.drop(columns="close"),
            periods=periods,
            config=_config(),
        )


@pytest.mark.parametrize("policy", ["strict", "ffill", "delay"])
def test_terminal_mark_does_not_silently_change_other_exit_policies(policy: str) -> None:
    positions, prices, periods = _inputs()
    with pytest.raises(ValueError, match=r"terminal.*period"):
        run_position_backtest(
            positions=positions,
            pricing=prices,
            periods=periods,
            config=replace(_config(), exit_price_policy=policy),
        )
