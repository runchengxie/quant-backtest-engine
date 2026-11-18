"""NAV order fee identification and dated fee quotation helpers."""

from __future__ import annotations

import pandas as pd

from ..dated_fees import DatedTradeFeeModel, FeeQuoteContext
from ..execution import SlippageModel
from .config import ExecutionSimConfig
from .models import (
    SupportedTradeFeeModel,
    _ExecutionTables,
    _NavOrder,
    _quote_trade_fee,
    _TradeFeeQuote,
)

TradeFeeModel = SupportedTradeFeeModel


def _nav_fee_order_id(order: _NavOrder) -> str:
    return "|".join(
        (
            order.rebalance_date.strftime("%Y%m%d"),
            order.entry_date.strftime("%Y%m%d"),
            order.side,
            order.symbol,
            str(order.start_idx),
        )
    )


def _nav_fee_group_id(order: _NavOrder, trade_date: pd.Timestamp) -> str:
    return f"{_nav_fee_order_id(order)}|{trade_date.strftime('%Y%m%d')}"


def _slippage_pricing_row(
    *,
    symbol: str,
    trade_date: pd.Timestamp,
    tables: _ExecutionTables,
    slippage_model: SlippageModel | None,
) -> pd.Series | None:
    if slippage_model is None:
        return None
    amount_col = str(getattr(slippage_model, "amount_col", "amount"))
    table = tables.liquidity_tables.get(amount_col)
    if table is None or trade_date not in table.index or symbol not in table.columns:
        return None
    return pd.Series({symbol: table.at[trade_date, symbol]}, dtype=float)


def _nav_trade_fee(
    fill: float,
    *,
    order: _NavOrder,
    trade_date: pd.Timestamp,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fee_group_notionals: dict[str, float],
) -> tuple[_TradeFeeQuote, str]:
    fee_group_id = _nav_fee_group_id(order, trade_date)
    dated_context = None
    if isinstance(trade_fee_model, DatedTradeFeeModel):
        dated_context = FeeQuoteContext(
            trade_date=trade_date,
            side=order.side,
            symbol=order.symbol,
            market=trade_fee_model.market_for(order.symbol),
            executed_notional=fill,
            cumulative_group_notional=fee_group_notionals.get(fee_group_id, 0.0),
        )
    quote = _quote_trade_fee(
        fill,
        side=order.side,
        cost_rate=cost_rate,
        fee_model=trade_fee_model,
        slippage_model=slippage_model,
        symbol=order.symbol,
        pricing_row=_slippage_pricing_row(
            symbol=order.symbol,
            trade_date=trade_date,
            tables=tables,
            slippage_model=slippage_model,
        ),
        portfolio_value=config.portfolio_value,
        dated_context=dated_context,
    )
    return quote, fee_group_id


def _accrue_nav_fee_quote(
    fee_group_notionals: dict[str, float],
    *,
    fee_group_id: str,
    fee_quote: _TradeFeeQuote,
) -> None:
    if fee_quote.cumulative_group_notional_after is not None:
        fee_group_notionals[fee_group_id] = fee_quote.cumulative_group_notional_after


__all__ = [
    "_accrue_nav_fee_quote",
    "_nav_fee_group_id",
    "_nav_fee_order_id",
    "_nav_trade_fee",
    "_slippage_pricing_row",
]
