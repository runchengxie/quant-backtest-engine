"""Snapshot-end, supplied-fill PAPER accounting; never a matcher or broker model.

Accrual uses opening inventory/marks and opening-available decimal annual rates,
ACT/365 elapsed calendar days (including fractional days). Dividends are supplied
per-share cash entitlements on opening inventory. All fills occur at snapshot end.
Locates are explicitly assumed quantity caps, not evidence of historical borrow.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class Observed:
    value: float
    available_at: pd.Timestamp


@dataclass(frozen=True)
class PaperFill:
    symbol: str
    quantity: float
    price: float
    timestamp: pd.Timestamp
    fee: float = 0.0


@dataclass(frozen=True)
class HouseMargin:
    long_haircut: float
    short_haircut: float
    short_proceeds_fraction: float


@dataclass(frozen=True)
class PaperState:
    as_of: pd.Timestamp
    cash: float
    quantities: Mapping[str, float]
    marks: Mapping[str, float]

    def __post_init__(self):
        object.__setattr__(self, "quantities", MappingProxyType(dict(self.quantities)))
        object.__setattr__(self, "marks", MappingProxyType(dict(self.marks)))


@dataclass(frozen=True)
class PaperProjection:
    state: PaperState
    nav: float
    weights: Mapping[str, float] | None
    gross_leverage: float | None
    net_leverage: float | None
    margin_required: float
    margin_excess: float
    margin_breach: bool
    restricted_proceeds: float
    borrow_cost: float
    financing_cost: float
    financing_basis: str
    financing_principal: float
    dividend_cash: float
    fill_fees: float
    elapsed_days: float
    borrow_breaches: tuple[str, ...]
    insolvent: bool
    paper_only: bool = field(default=True, init=False)
    executable: bool = field(default=False, init=False)


def _timestamp(value):
    if not isinstance(value, pd.Timestamp) or pd.isna(value) or value.tzinfo is None:
        raise ValueError("timestamps must be aware pd.Timestamp values")
    return value


def _number(value, *, minimum=None, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("values must be finite numbers")
    if (minimum is not None and value < minimum) or (positive and value <= 0):
        raise ValueError("value outside permitted range")
    return float(value)


def _symbol(symbol):
    if not isinstance(symbol, str) or not symbol.strip() or symbol != symbol.strip():
        raise ValueError("symbol must be a nonempty trimmed string")


def _observed(values, symbol, clock, max_age, *, positive=False):
    if symbol not in values:
        raise ValueError(f"missing input: {symbol}")
    observation = values[symbol]
    age = clock - _timestamp(observation.available_at)
    if age < pd.Timedelta(0) or age > max_age:
        raise ValueError(f"future or stale input: {symbol}")
    return _number(observation.value, minimum=0, positive=positive)


def _inventory(state, mappings):
    quantities = {}
    for symbol, quantity in state.quantities.items():
        _symbol(symbol)
        quantity = _number(quantity)
        if quantity:
            quantities[symbol] = quantity
    for symbol, price in state.marks.items():
        _symbol(symbol)
        _number(price, positive=True)
    for mapping in mappings:
        for symbol in mapping:
            _symbol(symbol)
    prior_marks = {}
    for symbol in quantities:
        if symbol not in state.marks:
            raise ValueError(f"missing prior mark: {symbol}")
        prior_marks[symbol] = _number(state.marks[symbol], positive=True)
    return quantities, prior_marks


def _apply_fills(quantities, fills, cash, shorts, start, end, rates, locates, max_age):
    fees = 0.0
    for fill in fills:
        _symbol(fill.symbol)
        if _timestamp(fill.timestamp) != end:
            raise ValueError("fill timestamp must equal endpoint as_of")
        quantity = _number(fill.quantity)
        price = _number(fill.price, positive=True)
        fee = _number(fill.fee, minimum=0)
        before = quantities.get(fill.symbol, 0)
        after = _number(before + quantity)
        if after < 0:
            shorts.add(fill.symbol)
            _observed(rates, fill.symbol, start, max_age)
            cap = _observed(locates, fill.symbol, end, max_age)
            if after < min(before, 0) and -after > cap:
                raise ValueError(f"assumed locate cap exceeded: {fill.symbol}")
        quantities[fill.symbol] = after
        cash = _number(cash - _number(quantity * price) - fee)
        fees = _number(fees + fee)
    return cash, fees


def _funding_principal(cash, quantities, prices, restriction, basis):
    if basis not in ("cash", "unrestricted_cash"):
        raise ValueError("financing_basis must be cash or unrestricted_cash")
    reserve = _number(sum(-q * prices[s] for s, q in quantities.items() if q < 0) * restriction)
    return _number(max(0, (reserve if basis == "unrestricted_cash" else 0) - cash))


def _accrue_opening(
    cash,
    quantities,
    prior_marks,
    start,
    days,
    borrow_rates,
    financing_rate,
    financing_basis,
    restriction,
    max_age,
    dividends,
):
    financing = _observed({"cash": financing_rate}, "cash", start, max_age)
    borrow_cost = 0.0
    shorts = set()
    for symbol, quantity in quantities.items():
        if quantity < 0:
            shorts.add(symbol)
            rate = _observed(borrow_rates, symbol, start, max_age)
            borrow_cost = _number(borrow_cost + -quantity * prior_marks[symbol] * rate * days / 365)
    financing_principal = _funding_principal(
        cash,
        quantities,
        prior_marks,
        restriction,
        financing_basis,
    )
    financing_cost = _number(financing_principal * financing * days / 365)
    dividend_cash = 0.0
    for symbol, amount in (dividends or {}).items():
        dividend_cash = _number(
            dividend_cash + quantities.get(symbol, 0) * _number(amount, minimum=0)
        )
    return borrow_cost, financing_cost, financing_principal, dividend_cash, shorts


def _interval(start, end, max_age):
    start, end = _timestamp(start), _timestamp(end)
    if (
        end < start
        or not isinstance(max_age, pd.Timedelta)
        or pd.isna(max_age)
        or max_age < pd.Timedelta(0)
    ):
        raise ValueError("invalid interval or max_age")
    return start, end


def project_paper_account(
    state: PaperState,
    *,
    as_of: pd.Timestamp,
    marks: Mapping[str, Observed],
    borrow_rates: Mapping[str, Observed],
    locate_quantities: Mapping[str, Observed],
    financing_rate: Observed,
    financing_basis: Literal["cash", "unrestricted_cash"],
    margin: HouseMargin,
    max_age: pd.Timedelta,
    fills: Sequence[PaperFill] = (),
    dividends: Mapping[str, float] | None = None,
) -> PaperProjection:
    """Mark prior state, accrue, then apply simultaneous endpoint fills.

    Rates are required for every opening or intrastep short, even for zero elapsed
    time; available_at must precede opening as_of. Locates are required for every
    opening/intrastep short at endpoint as_of. A recall never prevents a cover.
    Restricted proceeds are an endpoint marked-short-value reserve diagnostic;
    they are already in cash and are never subtracted again from NAV. House margin
    is long/short marked value times caller haircuts, compared with NAV. No forced
    liquidation or executable claim is made. Nonpositive NAV has no weights.
    Financing uses opening negative cash or opening cash less the marked short
    reserve, selected explicitly; this is an assumed funding model, not broker terms.
    """
    start, end = _interval(state.as_of, as_of, max_age)
    cash = _number(state.cash)
    haircuts = [
        _number(x, minimum=0)
        for x in (margin.long_haircut, margin.short_haircut, margin.short_proceeds_fraction)
    ]
    quantities, prior_marks = _inventory(
        state,
        (marks, borrow_rates, locate_quantities, dividends or {}),
    )
    days = (end - start).total_seconds() / 86400
    borrow_cost, financing_cost, financing_principal, dividend_cash, shorts = _accrue_opening(
        cash,
        quantities,
        prior_marks,
        start,
        days,
        borrow_rates,
        financing_rate,
        financing_basis,
        haircuts[2],
        max_age,
        dividends,
    )
    cash = _number(cash + dividend_cash - borrow_cost - financing_cost)
    cash, fill_fees = _apply_fills(
        quantities,
        fills,
        cash,
        shorts,
        start,
        end,
        borrow_rates,
        locate_quantities,
        max_age,
    )
    breaches = []
    for symbol in sorted(shorts):
        cap = _observed(locate_quantities, symbol, end, max_age)
        if -quantities.get(symbol, 0) > cap:
            breaches.append(symbol)
    quantities = {s: q for s, q in quantities.items() if q}
    current_marks = {s: _observed(marks, s, end, max_age, positive=True) for s in quantities}
    values = {s: _number(q * current_marks[s]) for s, q in quantities.items()}
    long_value = _number(sum(max(v, 0) for v in values.values()))
    short_value = _number(sum(max(-v, 0) for v in values.values()))
    gross_value = _number(long_value + short_value)
    net_value = _number(long_value - short_value)
    nav = _number(cash + net_value)
    required = _number(long_value * haircuts[0] + short_value * haircuts[1])
    insolvent = nav <= 0
    weights = (
        None if insolvent else MappingProxyType({s: _number(v / nav) for s, v in values.items()})
    )
    return PaperProjection(
        PaperState(end, _number(cash), quantities, current_marks),
        nav,
        weights,
        None if insolvent else _number(gross_value / nav),
        None if insolvent else _number(net_value / nav),
        required,
        _number(nav - required),
        nav < required,
        _number(short_value * haircuts[2]),
        borrow_cost,
        financing_cost,
        financing_basis,
        financing_principal,
        dividend_cash,
        fill_fees,
        days,
        tuple(breaches),
        insolvent,
    )
