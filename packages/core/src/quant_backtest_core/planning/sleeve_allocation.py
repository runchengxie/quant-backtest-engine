# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/portfolio/sleeve_allocation.py
# Original SHA256: 6916287aed000cc3a6d349c8ce83ae2c4ee6d43158333eddbf68b56eb7d83577
"""Pure single-batch shared-account attribution, with no execution or lifetime ledger."""

from collections import defaultdict
from dataclasses import dataclass, replace
from decimal import Decimal

from quant_backtest_core.evidence._exact import _clock, _decimal, _exact


@dataclass(frozen=True)
class SleeveDemand:
    """One reserved sleeve/symbol request; balances are supplied pre-batch evidence.

    Cash is reserved exclusively for this row (no reuse across rows/batches).
    Buy capacity reserves fee_budget and max_buy_price before netting. Sell
    capacity is sellable minus its locked subset, with sellable <= inventory. blocked
    prohibits both directions including internal transfers. Integer trade lots
    exclude fractional entitlements. Restrictions must be valid for the batch.
    """

    sleeve: str
    symbol: str
    quantity: int
    cash_budget: Decimal | str
    inventory: int
    sellable: int
    locked: int
    max_buy_price: Decimal | str | None = None
    fee_budget: Decimal | str = "0"
    lot_size: int = 1
    blocked: bool = False


@dataclass(frozen=True)
class ExternalOrder:
    symbol: str
    side: str
    quantity: int
    lot_size: int


@dataclass(frozen=True)
class SleeveNetPlan:
    demands: tuple[SleeveDemand, ...]
    reference_prices: tuple[tuple[str, Decimal], ...]
    internal_quantities: tuple[int, ...]
    external_demands: tuple[int, ...]
    external_orders: tuple[ExternalOrder, ...]


@dataclass(frozen=True)
class RecordedFill:
    """Consumed monetary provenance, normalized by Decimal(str(value)), never rounded."""

    fill_id: str
    ts_ns: int
    symbol: str
    side: str
    quantity: int
    price: Decimal
    gross_amount: Decimal
    fee: Decimal


@dataclass(frozen=True)
class SleeveDelta:
    sleeve: str
    symbol: str
    internal_quantity: int
    external_quantity: int
    quantity_delta: int
    cash_delta: Decimal
    fee: Decimal
    residual: int


@dataclass(frozen=True)
class SleeveAllocation:
    """Batch deltas only: internal cash sums to zero, external fees debited once.

    Add deltas to caller-owned initial sleeve balances to reconcile pooled state.
    PnL needs supplied cost bases/marks; this object never invents lifetime PnL.
    """

    deltas: tuple[SleeveDelta, ...]
    pooled_quantities: tuple[tuple[str, int], ...]
    pooled_cash_delta: Decimal
    pooled_fee: Decimal
    fills: tuple[RecordedFill, ...]


def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty sleeve, symbol and fill identity required")
    return value


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("bounded integer shares/lots required")
    return value


def _fee(value):
    number = _decimal(value, minimum=0)
    if number * 100 != (number * 100).to_integral_value():
        raise ValueError("actual fee and fee reservation must be whole nonnegative cents")
    return number


def _demand(row, reference):
    if type(row) is not SleeveDemand:
        raise ValueError("SleeveDemand declarations required")
    _name(row.sleeve)
    _name(row.symbol)
    if type(row.quantity) is not int or not row.quantity:
        raise ValueError("nonzero signed integer demand required")
    lot = _integer(row.lot_size, 1)
    if abs(row.quantity) % lot:
        raise ValueError("demand must contain whole trade lots")
    for value in (row.inventory, row.sellable, row.locked):
        _integer(value)
    if not 0 <= row.locked <= row.sellable <= row.inventory or type(row.blocked) is not bool:
        raise ValueError("inventory, sellability, locks and blocked flag are inconsistent")
    cash, fee = _decimal(row.cash_budget, minimum=0), _fee(row.fee_budget)
    if cash < fee:
        raise ValueError("cash budget must reserve the declared fee budget")
    price = None
    if row.quantity > 0:
        if row.max_buy_price is None:
            raise ValueError("explicit maximum buy price required")
        price = _decimal(row.max_buy_price, minimum=reference)
        capacity = int((cash - fee) // (price * lot)) * lot
    else:
        if row.max_buy_price is not None:
            raise ValueError("sell rows do not support maximum buy prices")
        capacity = (row.sellable - row.locked) // lot * lot
    quantity = min(abs(row.quantity), capacity) if not row.blocked else 0
    return replace(row, cash_budget=cash, fee_budget=fee, max_buy_price=price), quantity


def _pro_rata(total, weights):
    """Hamilton whole units, descending exact remainder then lexical input key."""
    denominator = sum(weights.values())
    if not total:
        return dict.fromkeys(weights, 0)
    result = {key: total * weight // denominator for key, weight in weights.items()}
    ranking = sorted(weights, key=lambda key: (-(total * weights[key] % denominator), key))
    for key in ranking[: total - sum(result.values())]:
        result[key] += 1
    return result


def _batch_inputs(demands, reference_prices):
    demands = tuple(demands)
    if not demands or any(type(row) is not SleeveDemand for row in demands):
        raise ValueError("nonempty SleeveDemand batch required")
    keys = [(r.sleeve, r.symbol) for r in demands]
    for sleeve, symbol in keys:
        _name(sleeve)
        _name(symbol)
    if len(keys) != len(set(keys)):
        raise ValueError("unique sleeve/symbol rows required")
    symbols = sorted({r.symbol for r in demands})
    if set(reference_prices) != set(symbols):
        raise ValueError("one explicit reference for each demanded symbol required")
    prices = {s: _decimal(reference_prices[s], minimum=0) for s in symbols}
    if any(not p for p in prices.values()):
        raise ValueError("positive reference prices required")
    return demands, prices, symbols


@_exact
def net_sleeve_demands(demands, *, reference_prices, policy="pro_rata"):
    """Net one long-only shared-account batch at positive supplied raw references.

    One row per sleeve/symbol, common lot per symbol. Pro rata works in lots;
    largest remainders win, with lexical sleeve ties. Internal crossing is
    reference-value attribution with no market fill, fee, impact or capacity.
    Each symbol has at most one residual aggregate external order. This plan
    does not submit orders, model a venue or admit independent broker accounts.
    """
    if policy != "pro_rata":
        raise ValueError("only pro_rata policy is supported")
    demands, prices, symbols = _batch_inputs(demands, reference_prices)
    normalized = [
        _demand(r, prices[r.symbol]) for r in sorted(demands, key=lambda r: (r.sleeve, r.symbol))
    ]
    rows = tuple(r for r, _ in normalized)
    internal, external, orders = [0] * len(rows), [0] * len(rows), []
    for symbol in symbols:
        indices = [i for i, r in enumerate(rows) if r.symbol == symbol]
        lots = {rows[i].lot_size for i in indices}
        if len(lots) != 1:
            raise ValueError("common lot per symbol required")
        lot = lots.pop()
        buys = {i: normalized[i][1] // lot for i in indices if rows[i].quantity > 0}
        sells = {i: normalized[i][1] // lot for i in indices if rows[i].quantity < 0}
        crossing = min(sum(buys.values()), sum(sells.values()))
        for sign, weights in ((1, buys), (-1, sells)):
            for i, units in _pro_rata(crossing, weights).items():
                internal[i] = sign * units * lot
                external[i] = sign * (weights[i] - units) * lot
        net = sum(external[i] for i in indices)
        if net:
            orders.append(ExternalOrder(symbol, "buy" if net > 0 else "sell", abs(net), lot))
    return SleeveNetPlan(
        rows, tuple(prices.items()), tuple(internal), tuple(external), tuple(orders)
    )


def _recorded_fills(fills):
    seen = {}
    for row in fills:
        try:
            fill = RecordedFill(
                _name(row["fill_id"]),
                _clock(row["ts_ns"]),
                _name(row["symbol"]),
                _name(row["side"]),
                _integer(row["quantity"], 1),
                _decimal(row["price"], minimum=0),
                _decimal(row["gross_amount"], minimum=0),
                _fee(row["fee"]),
            )
        except (KeyError, TypeError) as error:
            raise ValueError("complete recorded physical fill fields required") from error
        if fill.side not in {"buy", "sell"} or not fill.price:
            raise ValueError("positive raw price and buy/sell side required")
        if fill.gross_amount != fill.quantity * fill.price:
            raise ValueError("recorded gross must exactly equal raw quantity times price")
        if fill.fill_id in seen and seen[fill.fill_id] != fill:
            raise ValueError("conflicting reports for physical fill identity")
        seen[fill.fill_id] = fill
    return tuple(sorted(seen.values(), key=lambda f: (f.ts_ns, f.fill_id)))


@_exact
def allocate_external_fills(net_plan, fills):
    """Attribute actual fills without mutation; reject the entire incompatible batch.

    Required physical fields: fill_id, ts_ns (positive UTC nanoseconds), symbol,
    side, integer quantity, positive raw price, gross_amount, fee (whole cents).
    Decimal(str(value)) preserves supplied values without rounding. Gross must
    equal quantity * price exactly; binary-owner adapters must declare their
    monetary normalization and retain source evidence. No fill is silently
    clipped or dropped. Identical duplicate identities deduplicate within this
    batch only; conflicting reports fail. Caller owns cross-batch deduplication.

    Canonical clock/ID ordering apportions each partial fill over remaining
    demand in whole lots. Fees are its recorded cents pro rata to that fill's
    allocated shares, with lexical sleeve ties. No parent fee is recalculated.
    Every buy price must fit each receiving row's maximum; cumulative fees and
    debits must fit reservations. No sale financing or fee redistribution.
    """
    if type(net_plan) is not SleeveNetPlan or net_plan != net_sleeve_demands(
        net_plan.demands, reference_prices=dict(net_plan.reference_prices)
    ):
        raise ValueError("unchanged net_sleeve_demands plan required")
    recorded = _recorded_fills(fills)
    rows = net_plan.demands
    references = dict(net_plan.reference_prices)
    remaining = list(net_plan.external_demands)
    external, fees = [0] * len(rows), [Decimal(0)] * len(rows)
    cash = [
        -q * references[r.symbol] for r, q in zip(rows, net_plan.internal_quantities, strict=True)
    ]
    orders = {o.symbol: o for o in net_plan.external_orders}
    pooled, pooled_cash, pooled_fee = defaultdict(int), Decimal(0), Decimal(0)
    for fill in recorded:
        order = orders.get(fill.symbol)
        if order is None or fill.side != order.side or fill.quantity % order.lot_size:
            raise ValueError("fill must match aggregate order side, symbol and whole lot")
        sign = 1 if fill.side == "buy" else -1
        weights = {
            i: abs(q) // order.lot_size
            for i, q in enumerate(remaining)
            if rows[i].symbol == fill.symbol and q
        }
        if fill.quantity > sum(weights.values()) * order.lot_size:
            raise ValueError("actual fills exceed aggregate residual demand")
        allocated = _pro_rata(fill.quantity // order.lot_size, weights)
        assigned_fees = _pro_rata(int(fill.fee * 100), {i: q for i, q in allocated.items() if q})
        for i, lots in allocated.items():
            if not lots:
                continue
            q = sign * lots * order.lot_size
            if sign > 0 and fill.price > rows[i].max_buy_price:
                raise ValueError("actual buy price exceeds sleeve maximum")
            external[i] += q
            remaining[i] -= q
            fees[i] += Decimal(assigned_fees[i]) / 100
            cash[i] -= q * fill.price + Decimal(assigned_fees[i]) / 100
            if fees[i] > rows[i].fee_budget:
                raise ValueError("actual fill exceeds sleeve fee reservation")
            if -cash[i] > rows[i].cash_budget:
                raise ValueError("actual fill exceeds sleeve cash reservation")
        pooled[fill.symbol] += sign * fill.quantity
        pooled_cash -= sign * fill.gross_amount + fill.fee
        pooled_fee += fill.fee
    deltas = tuple(
        SleeveDelta(
            r.sleeve,
            r.symbol,
            internal,
            ext,
            internal + ext,
            c,
            fee,
            r.quantity - internal - ext,
        )
        for r, internal, ext, c, fee in zip(
            rows, net_plan.internal_quantities, external, cash, fees, strict=True
        )
    )
    return SleeveAllocation(
        deltas, tuple(sorted(pooled.items())), pooled_cash, pooled_fee, recorded
    )
