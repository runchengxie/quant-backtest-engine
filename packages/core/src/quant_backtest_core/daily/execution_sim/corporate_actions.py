"""Run-local rights ledger; orders, fills and cash constraints remain in the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from quant_backtest_core._minute.corporate_actions import CorporateAction

from .capacity import _price_at, _valuation_price

if TYPE_CHECKING:
    from .models import _AdjustedNavLedger, _ExecutionTables


ACTION_COLUMNS = [
    "trade_date",
    "event_id",
    "symbol",
    "stage",
    "available_date",
    "record_date",
    "ex_date",
    "cash_pay_date",
    "stock_tradable_date",
    "record_shares",
    "cash_per_share",
    "stock_per_share",
    "withholding_rate",
    "gross_cash",
    "withheld_cash",
    "net_cash",
    "stock_shares",
    "cash_receivable",
    "stock_receivable_shares",
]
HOLDING_COLUMNS = [
    "trade_date",
    "symbol",
    "shares",
    "sellable_shares",
    "raw_mark",
    "held_value",
    "cash_receivable",
    "stock_receivable_shares",
    "stock_receivable_value",
]
RECEIVABLE_COLUMNS = ["cash_receivable", "stock_receivable_value"]


@dataclass
class _Right:
    event: CorporateAction
    record_shares: float | None = None
    cash: float = 0.0
    stock: float = 0.0


@dataclass
class _CorporateActionLedger:
    events: tuple[CorporateAction, ...]
    sessions: list[pd.Timestamp]
    rights: list[_Right] = field(init=False)
    action_rows: list[dict[str, Any]] = field(default_factory=list)
    holding_rows: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        calendar = set(self.sessions)
        for event in self.events:
            for name in ("record_date", "ex_date", "cash_pay_date", "stock_tradable_date"):
                value = getattr(event, name)
                if (
                    value is not None
                    and self.sessions[0] <= value <= self.sessions[-1]
                    and value not in calendar
                ):
                    raise ValueError(
                        f"corporate action {event.event_id}: {name} absent from calendar"
                    )
        self.rights = [_Right(event) for event in self.events]

    def _receipt(self, right: _Right, day: pd.Timestamp, stage: str) -> None:
        event = right.event
        quantity = float(right.record_shares or 0.0)
        gross = quantity * event.cash_per_share
        withheld = gross * event.withholding_rate
        self.action_rows.append(
            {
                "trade_date": day.strftime("%Y%m%d"),
                "event_id": event.event_id,
                "symbol": event.symbol,
                "stage": stage,
                **{
                    name: (
                        getattr(event, name).strftime("%Y%m%d")
                        if getattr(event, name) is not None
                        else None
                    )
                    for name in (
                        "available_date",
                        "record_date",
                        "ex_date",
                        "cash_pay_date",
                        "stock_tradable_date",
                    )
                },
                "record_shares": quantity,
                "cash_per_share": event.cash_per_share,
                "stock_per_share": event.stock_per_share,
                "withholding_rate": event.withholding_rate,
                "gross_cash": gross,
                "withheld_cash": withheld,
                "net_cash": gross - withheld,
                "stock_shares": quantity * event.stock_per_share,
                "cash_receivable": right.cash,
                "stock_receivable_shares": right.stock,
            }
        )

    def open_day(self, ledger: _AdjustedNavLedger, day: pd.Timestamp) -> set[str]:
        affected = {event.symbol for event in self.events if event.ex_date == day}
        for right in self.rights:
            event = right.event
            if right.record_shares is None:
                continue  # Cash-only start: no imported record-date ownership.
            if event.ex_date == day:
                right.cash = (
                    right.record_shares * event.cash_per_share * (1 - event.withholding_rate)
                )
                right.stock = right.record_shares * event.stock_per_share
                self._receipt(right, day, "ex")
            if event.cash_per_share > 0 and event.cash_pay_date == day:
                ledger.cash += right.cash
                right.cash = 0.0
                self._receipt(right, day, "cash_payment")
            if event.stock_per_share > 0 and event.stock_tradable_date == day:
                if right.stock > 0:
                    ledger.shares[event.symbol] = ledger.shares.get(event.symbol, 0.0) + right.stock
                right.stock = 0.0
                self._receipt(right, day, "stock_release")
        return affected

    def capture_close(self, ledger: _AdjustedNavLedger, day: pd.Timestamp) -> None:
        for right in self.rights:
            if right.event.record_date == day:
                right.record_shares = float(ledger.shares.get(right.event.symbol, 0.0))
                self._receipt(right, day, "record")

    def stock_by_symbol(self) -> dict[str, float]:
        stocks: dict[str, float] = {}
        for right in self.rights:
            if right.stock > 0:
                symbol = right.event.symbol
                stocks[symbol] = stocks.get(symbol, 0.0) + right.stock
        return stocks

    def validate_marks(
        self,
        ledger: _AdjustedNavLedger,
        day: pd.Timestamp,
        tables: _ExecutionTables,
    ) -> None:
        required = set(self.stock_by_symbol())
        for right in self.rights:
            event = right.event
            end = pd.Timestamp(
                max(
                    value
                    for value in (event.ex_date, event.cash_pay_date, event.stock_tradable_date)
                    if value is not None
                )
            )
            record_date = pd.Timestamp(event.record_date)
            if record_date <= day <= end and ledger.shares.get(event.symbol, 0.0) > 0:
                required.add(event.symbol)
        for symbol in required:
            if not np.isfinite(_price_at(symbol, day, tables.price_table)):
                raise ValueError(
                    f"missing valid raw mark for corporate action: {symbol} on {day.date()}"
                )

    def values(self, day: pd.Timestamp, tables: _ExecutionTables) -> tuple[float, float]:
        cash = sum(right.cash for right in self.rights)
        stock = sum(
            quantity * _price_at(symbol, day, tables.price_table)
            for symbol, quantity in self.stock_by_symbol().items()
        )
        return float(cash), float(stock)

    def snapshot(
        self,
        ledger: _AdjustedNavLedger,
        day: pd.Timestamp,
        tables: _ExecutionTables,
    ) -> None:
        stocks = self.stock_by_symbol()
        cash: dict[str, float] = {}
        for right in self.rights:
            if right.cash > 0:
                symbol = right.event.symbol
                cash[symbol] = cash.get(symbol, 0.0) + right.cash
        for symbol in sorted(set(ledger.shares) | set(stocks) | set(cash)):
            shares = float(ledger.shares.get(symbol, 0.0))
            price = _valuation_price(symbol, day, tables.price_table, ledger.last_prices)
            available = (
                shares
                if ledger.t1_available is None
                else min(shares, ledger.t1_available.get(symbol, 0.0))
            )
            stock_shares = stocks.get(symbol, 0.0)
            self.holding_rows.append(
                {
                    "trade_date": day.strftime("%Y%m%d"),
                    "symbol": symbol,
                    "shares": shares,
                    "sellable_shares": available,
                    "raw_mark": price,
                    "held_value": shares * price if shares else 0.0,
                    "cash_receivable": cash.get(symbol, 0.0),
                    "stock_receivable_shares": stock_shares,
                    "stock_receivable_value": stock_shares * price if stock_shares else 0.0,
                }
            )

    def frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        return (
            pd.DataFrame(self.action_rows, columns=ACTION_COLUMNS),
            pd.DataFrame(self.holding_rows, columns=HOLDING_COLUMNS),
        )


def _action_conventions() -> dict[str, Any]:
    return {
        "price_basis": "raw",
        "entitlement": "record_date_closing_held_shares",
        "recognition": "ex_date_before_orders",
        "settlement": "before_orders",
        "outstanding_orders": "cancel_affected_symbol_on_ex_date",
        "fractional_shares": "retained_no_cash_in_lieu",
        "withholding": "explicit_event_flat_rate_not_holding_period_tax",
        "calendar": "supplied_execution_table_sessions_no_date_rolling",
    }
