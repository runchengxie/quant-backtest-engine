"""Synthetic exit checks for simulated fills near a delisting date."""

import pandas as pd
import pytest

from quant_backtest_core.daily.execution_sim import audit_delisting_exits


def _marks() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"trade_date": "20260622", "symbol": "600599.SH", "adjusted_close": 0.43},
            {"trade_date": "20260625", "symbol": "000001.SZ", "adjusted_close": 10.0},
            {"trade_date": "20260626", "symbol": "000001.SZ", "adjusted_close": 10.0},
        ]
    )


def _fills(sell_notional: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": "20260622",
                "symbol": "600599.SH",
                "side": "buy",
                "filled_notional": 43.0,
            },
            {
                "trade_date": "20260622",
                "symbol": "600599.SH",
                "side": "sell",
                "filled_notional": sell_notional,
            },
        ]
    )


def test_delisting_exit_accepts_full_pre_delist_sale() -> None:
    result = audit_delisting_exits(
        _fills(43.0), _marks(), {"600599.SH": "20260626"}, price_col="adjusted_close"
    )
    assert result.to_dict("records") == [
        {
            "symbol": "600599.SH",
            "delist_date": "20260626",
            "residual_quantity": 0.0,
            "status": "passed",
        }
    ]


def test_delisting_exit_blocks_residual_shares() -> None:
    with pytest.raises(ValueError, match="unsettled simulated delisting exposure"):
        audit_delisting_exits(
            _fills(21.5), _marks(), {"600599.SH": "20260626"}, price_col="adjusted_close"
        )


def test_delisting_exit_blocks_late_trade_and_missing_mark() -> None:
    late = _fills(43.0)
    late.loc[1, "trade_date"] = "20260626"
    with pytest.raises(ValueError, match="valid execution mark"):
        audit_delisting_exits(late, _marks(), {"600599.SH": "20260626"}, price_col="adjusted_close")


def test_delisting_exit_blocks_late_trade_with_mark() -> None:
    late = _fills(43.0)
    late.loc[1, "trade_date"] = "20260626"
    marks = pd.concat(
        [
            _marks(),
            pd.DataFrame(
                [
                    {
                        "trade_date": "20260626",
                        "symbol": "600599.SH",
                        "adjusted_close": 0.43,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="unsettled simulated delisting exposure"):
        audit_delisting_exits(late, marks, {"600599.SH": "20260626"}, price_col="adjusted_close")


def test_delisting_exit_accepts_unowned_delisted_name() -> None:
    fills = pd.DataFrame(columns=["trade_date", "symbol", "side", "filled_notional"])
    result = audit_delisting_exits(
        fills, _marks(), {"600599.SH": "20260626"}, price_col="adjusted_close"
    )
    assert result.loc[0, "status"] == "passed"
    assert result.loc[0, "residual_quantity"] == 0.0
