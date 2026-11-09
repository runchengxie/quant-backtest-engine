# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/_portfolio/minute_execution.py
# Original SHA256: ea4e3d1db80b90647185942d2de6935f57f29db569ab9e4b4070d210b3654bb9
"""Opt-in raw-price minute execution using disclosed bar VWAP proxies.

Durations are wall-clock minutes. Bars are end-stamped; no order can use a
bar starting at or before its release plus latency. No queue or impact model.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

import pandas as pd

from ._minute_state import MinuteDecisionState as MinuteDecisionState
from ._minute_validation import (
    _validate as _validate,
)
from ._minute_validation import (
    _validate_bar_numbers as _validate_bar_numbers,
)
from ._minute_validation import (
    _validate_intervals as _validate_intervals,
)
from ._minute_validation import (
    _validate_target_weights as _validate_target_weights,
)
from .capital_flows import (
    CAPITAL_FLOW_COLUMNS,
    apply_capital_flows,
    capital_daily,
    initialize_capital,
)
from .corporate_actions import CorporateAction, normalize_corporate_actions
from .valuation_events import (
    VALUATION_LEDGER_COLUMNS,
    minute_valuation_provenance,
    normalize_valuation_events,
)
from .valuation_events import ValuationEvent as ValuationEvent


@dataclass(frozen=True)
class MinuteExecutionConfig:
    """Fees are basis points of actual fills; durations use elapsed wall time.

    Slices release at ``entry + i * execution_minutes / release_slices`` for
    i=0..slices-1; unused released quantities carry until the deadline.
    An optional commission minimum is charged once per parent across partial
    fills. sell_fee_bp includes sell_tax_bp; tax is outside the commission floor.
    """

    initial_cash: float
    participation_rate: float
    buy_fee_bp: float
    sell_fee_bp: float
    lot_size: int = 100
    release_slices: int = 1
    execution_minutes: int = 30
    latency_minutes: int = 1
    commission_minimum_cny: float = 0.0
    sell_tax_bp: float = 0.0

    def __post_init__(self):
        for name in (
            "initial_cash",
            "participation_rate",
            "buy_fee_bp",
            "sell_fee_bp",
            "latency_minutes",
            "commission_minimum_cny",
            "sell_tax_bp",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {name}")
        if self.initial_cash <= 0 or not 0 < self.participation_rate <= 1:
            raise ValueError("cash and participation must be positive; participation <= 1")
        for name in ("lot_size", "release_slices", "execution_minutes"):
            value = getattr(self, name)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.sell_tax_bp > self.sell_fee_bp:
            raise ValueError("sell_tax_bp cannot exceed sell_fee_bp")
        if self.sell_fee_bp >= 10000:
            raise ValueError("sell fee must be below proceeds")


@dataclass
class MinuteExecutionResult:
    """Inspectable ledgers; daily transaction_cost is cumulative since inception."""

    daily: pd.DataFrame
    orders: pd.DataFrame
    fills: pd.DataFrame
    summary: dict
    holdings: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["date", "symbol", "quantity"])
    )
    valuation_ledger: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=VALUATION_LEDGER_COLUMNS)
    )
    capital_flow_ledger: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=CAPITAL_FLOW_COLUMNS)
    )


def simulate_minute_execution(
    targets,
    bars,
    config,
    *,
    corporate_actions=(),
    valuation_events=(),
    capital_flows=(),
    decision_policy=None,
    impact_model=None,
):
    """Complete target snapshots; quantities fixed from marks known at entry.

    ``targets`` has aware decision_time/entry_time, symbol and weight; each entry
    is a complete portfolio snapshot, so omitted holdings receive a zero target.
    Optional order_type declares market only: conditional orders requiring an
    intrabar path are rejected. Optional information_time declares the latest
    information used for a decision and must be aware and <= decision_time.
    Omitting it retains the caller's responsibility for point-in-time inputs.
    Entry must follow decision. ``bars`` uses aware end-stamped time, symbol,
    raw OHLC, volume in shares, amount in currency, up_limit/down_limit and a
    strict boolean tradable. Optional interval_start is aware and precedes time;
    otherwise it defaults to time minus one minute. The entire interval must
    start strictly after each release plus latency. Nontradable bars mark close.

    Sizing uses strictly earlier observed marks. Missing marks prevent orders;
    a held symbol missing that day's final observations makes daily NAV missing
    and is listed in stale_mark_symbols. Actual fills use bounded amount/volume
    proxies, shared bar participation, whole lots, T+1 and fee-aware cash checks.
    Conservative side-specific limit touches block the entire bar. This does
    not reproduce auction/queue matching, intrabar paths, market impact or taxes.

    Optional paired mark_source_time/mark_basis columns declare provenance. Raw
    marks retain their bar timestamp. declared_nontrading marks are zero-volume,
    nontradable flat-price valuation observations with source time <= bar time;
    they do not permanently prohibit subsequent trading or certify the caller's
    source/event policy. Source time and basis appear in later order references.

    Known ex-date distributions adjust prior marks by (mark-gross_cash)/(1+stock)
    before sizing; orders disclose the synthetic basis and effective/source times.
    Unreleased ex-recognized stock rights count toward target economic exposure.
    CorporateAction events require observed record-date coverage. Record-day
    closing holdings create rights; ex dates recognize receivables, and payments
    and stock availability credit them on the first observed subsequent day.
    Stock rights retain exact quantities. Full exits allow integer odd lots;
    fractional shares remain unsellable and are disclosed in summary.
    A superseding snapshot cancels all unfilled pending orders explicitly.

    decision_policy(state, proposed_weights) optionally computes complete weights
    at decision_time using strictly earlier observations and synchronous economic
    account state. Returned None preserves existing orders at entry; an empty
    mapping exits all holdings. Weights freeze until entry. Snapshots are read-only.

    impact_model is an optional uncalibrated LinearImpact research stress model.
    It changes actual fill prices and later fills, never adds a duplicate cash fee.
    Raw valuation and strategy marks remain external historical observations;
    this is execution-price stress, not an endogenous market or feature simulator.
    Impacted prices outside historical price limits cannot fill.

    Optional ValuationEvent declarations establish permanent nontrading states.
    Apply at effective time before sizing, preserving cash and legal inventory.
    Declared marks persist and only later events replace them; nontradable bars
    are ignored for affected marks, while conflicting tradable bars are rejected.
    A pre-window declaration applies at the first base instant with original
    provenance. Future events are ignored without extending the simulation.
    Opt-in valuation_marks and valuation_ledger expose source/effective times and
    age; declared persistence never claims observed daily quote freshness.
    """
    simulation = _MinuteSimulation(targets, bars, config, corporate_actions, valuation_events)
    simulation.decision_policy = decision_policy
    simulation.impact_model = impact_model
    if decision_policy is not None:
        simulation.times = sorted(set(simulation.times) | set(simulation.decisions))
        simulation.ignored_future_event_ids = []
        simulation.scheduled_valuations = simulation.schedule_valuations()
        simulation.times = sorted(set(simulation.times) | set(simulation.scheduled_valuations))
    initialize_capital(simulation, capital_flows)
    return simulation.run()


class _MinuteSimulation:
    scheduled_capital_flows: dict[pd.Timestamp, list]
    capital_flow_ledger: list[dict]

    def __init__(self, targets, bars, config, corporate_actions, valuation_events):
        self.targets = targets
        self.bars = bars.copy()
        if "interval_start" not in self.bars and "time" in self.bars:
            self.bars["interval_start"] = self.bars.time - pd.Timedelta(minutes=1)
        self.config = config
        self.corporate_actions = corporate_actions
        _validate(self.targets, self.bars)
        self.valuation_events = normalize_valuation_events(
            valuation_events, self.bars, self.targets
        )
        self.valuation_state = {}
        self.valuation_ledger = []
        self.ignored_future_event_ids = []
        self.actions: tuple[CorporateAction, ...] = tuple(self.corporate_actions)
        if any(not isinstance(a, CorporateAction) for a in self.actions):
            raise ValueError("corporate actions must be CorporateAction events")
        self.actions = cast(
            tuple[CorporateAction, ...], normalize_corporate_actions(self.actions, "raw")
        )
        self.rights = {}
        if self.actions and (
            self.bars.empty
            or any(
                cast(pd.Timestamp, a.record_date).date() < self.bars.time.min().date()
                for a in self.actions
            )
        ):
            raise ValueError("corporate action record dates require history coverage")
        self.cash = float(self.config.initial_cash)
        self.holdings, self.bought, self.marks = ({}, {}, {})
        self.orders, self.fills, self.daily = ([], [], [])
        self.costs = 0.0
        self.mark_days = {}
        self.mark_times = {}
        self.mark_source_times = {}
        self.mark_basis = {}
        self.adjusted_ex_dates = set()
        self.holdings_ledger = []
        self.clipped_vwap_bars = 0
        self.snapshots = dict(list(self.targets.groupby("entry_time", sort=True)))
        self.grouped = dict(list(self.bars.groupby("time", sort=True)))
        self.times = sorted(set(self.snapshots) | set(self.grouped))
        self.scheduled_valuations = self.schedule_valuations()
        self.times = sorted(set(self.times) | set(self.scheduled_valuations))
        self.current_time = None
        self.current_day = None
        self.day_has_events = False
        self.pending = []
        self.execution_locked_symbols: tuple[str, ...] = ()
        self.bar_execution_locked_symbols: tuple[str, ...] = ()
        self.decision_policy = None
        self.impact_model = None
        self.decisions = {}
        self.policy_snapshots = {}
        for entry, snapshot in self.snapshots.items():
            decision = snapshot.decision_time.iloc[0]
            self.decisions.setdefault(decision, []).append(entry)

        initialize_capital(self, ())

    def value(self):
        if any((s not in self.marks for s, q in self.holdings.items() if q)):
            return float("nan")
        return sum((q * self.marks[s] for s, q in self.holdings.items() if q))

    def receivables(self):
        cash_right = sum(r["cash"] for r in self.rights.values() if r["ex"])
        stock_right = sum(
            r["stock"] * self.marks.get(r["symbol"], float("nan"))
            for r in self.rights.values()
            if r["ex"] and r["stock"]
        )
        return (cash_right, stock_right)

    def close_day(self):
        self.holdings_ledger.extend(
            {"date": self.current_day, "symbol": s, "quantity": q}
            for s, q in sorted(self.holdings.items())
            if q > 0
        )
        for action in self.actions:
            if cast(pd.Timestamp, action.record_date).date() == self.current_day:
                q = self.holdings.get(action.symbol, 0)
                self.rights[action.event_id] = {
                    "symbol": action.symbol,
                    "cash": q * action.cash_per_share * (1 - action.withholding_rate),
                    "stock": q * action.stock_per_share,
                    "ex": False,
                }
        stale_holdings = {s for s, q in self.holdings.items() if q and self.stale_mark(s)}
        stale_rights = {
            r["symbol"]
            for r in self.rights.values()
            if r["ex"] and r["stock"] and self.stale_mark(r["symbol"])
        }
        stale = sorted(stale_holdings | stale_rights)
        pv = float("nan") if stale_holdings else self.value()
        cr, sr = self.receivables()
        if stale_rights:
            sr = float("nan")
        self.daily.append(
            {
                "date": self.current_day,
                "stale_mark_symbols": tuple(stale),
                "cash": self.cash,
                "positions_value": pv,
                "cash_receivable": cr,
                "stock_receivable_value": sr,
                "nav": self.cash + pv + cr + sr,
                "transaction_cost": self.costs,
            }
        )
        capital_daily(self, self.daily[-1])
        if self.valuation_events:
            self.daily[-1]["valuation_marks"] = minute_valuation_provenance(self)

    def stale_mark(self, symbol):
        return symbol not in self.valuation_state and self.mark_days.get(symbol) != self.current_day

    def schedule_valuations(self):
        if not self.times:
            self.ignored_future_event_ids = [e.event_id for e in self.valuation_events]
            return {}
        scheduled = {}
        first, last = self.times[0], self.times[-1]
        for event in self.valuation_events:
            effective = cast(pd.Timestamp, event.effective_time)
            if effective > last:
                self.ignored_future_event_ids.append(event.event_id)
                continue
            scheduled.setdefault(max(first, effective), []).append(event)
        return scheduled

    def apply_valuations(self, time):
        for event in self.scheduled_valuations.get(time, ()):
            symbol = event.symbol
            previous = self.marks.get(symbol, float("nan"))
            quantity = self.holdings.get(symbol, 0)
            rights = self.stock_exposure(symbol) - quantity
            self.valuation_ledger.append(
                {
                    "time": time,
                    "event_id": event.event_id,
                    "symbol": symbol,
                    "effective_time": event.effective_time,
                    "available_time": event.available_time,
                    "value_per_share": event.value_per_share,
                    "previous_value_per_share": previous,
                    "basis": event.basis,
                    "source": event.source,
                    "quantity": quantity,
                    "stock_receivable_quantity": rights,
                    "delta_value": (quantity + rights) * (event.value_per_share - previous)
                    if quantity + rights
                    else 0.0,
                    "cash_before": self.cash,
                    "cash_after": self.cash,
                }
            )
            self.valuation_state[symbol] = event
            self.marks[symbol] = event.value_per_share
            self.mark_basis[symbol] = "nontrading_valuation:" + event.basis
            self.mark_times[symbol] = event.effective_time
            self.mark_source_times[symbol] = event.available_time
            for order in self.pending:
                if order["symbol"] == symbol and order["status"] == "pending":
                    order.update(status="cancelled", reason="nontrading_valuation")

    def adjust_ex_references(self, day):
        groups = {}
        for action in self.actions:
            key = (action.symbol, cast(pd.Timestamp, action.ex_date).date())
            if key in self.adjusted_ex_dates or cast(pd.Timestamp, action.ex_date).date() > day:
                continue
            cash, stock = groups.get(key, (0, 0))
            groups[key] = (cash + action.cash_per_share, stock + action.stock_per_share)
        for (symbol, ex_date), (cash, stock) in sorted(
            groups.items(), key=lambda item: (item[0][1], item[0][0])
        ):
            self.adjusted_ex_dates.add((symbol, ex_date))
            if (
                symbol in self.valuation_state
                or symbol not in self.marks
                or self.mark_days[symbol] >= ex_date
            ):
                continue
            reference = (self.marks[symbol] - cash) / (1 + stock)
            if reference <= 0:
                raise ValueError("corporate action implies nonpositive ex reference")
            self.marks[symbol] = reference
            self.mark_basis[symbol] = "synthetic_ex_reference"
            self.mark_times[symbol] = pd.Timestamp(ex_date, tz=self.mark_times[symbol].tz)

    def stock_exposure(self, symbol):
        return self.holdings.get(symbol, 0) + sum(
            r["stock"] for r in self.rights.values() if r["ex"] and r["symbol"] == symbol
        )

    def open_day(self, day):
        self.adjust_ex_references(day)
        for action in self.actions:
            right = self.rights.get(action.event_id)
            if right is None:
                if (
                    cast(pd.Timestamp, action.record_date).date() < day
                    and cast(pd.Timestamp, action.record_date).date() >= self.times[0].date()
                ):
                    raise ValueError("corporate action record-date closing coverage missing")
                continue
            if cast(pd.Timestamp, action.ex_date).date() <= day:
                right["ex"] = True
            if (
                action.cash_pay_date is not None
                and cast(pd.Timestamp, action.cash_pay_date).date() <= day
            ):
                self.cash += right["cash"]
                right["cash"] = 0
            if (
                action.stock_tradable_date is not None
                and cast(pd.Timestamp, action.stock_tradable_date).date() <= day
            ):
                self.holdings[action.symbol] = self.holdings.get(action.symbol, 0) + right["stock"]
                right["stock"] = 0

    def decide(self, time):
        cr, sr = self.receivables()
        state = MinuteDecisionState(
            time=time,
            cash=self.cash,
            nav=self.cash + self.value() + cr + sr,
            holdings=MappingProxyType(dict(self.holdings)),
            marks=MappingProxyType(dict(self.marks)),
            mark_times=MappingProxyType(dict(self.mark_times)),
            pending_orders=tuple(
                MappingProxyType({**o, "remaining_quantity": o["quantity"] - o["filled_quantity"]})
                for o in self.pending
                if o["status"] == "pending" and time <= o["deadline"]
            ),
            cash_receivable=cr,
            stock_receivable_value=sr,
            locked_symbols=tuple(sorted(getattr(self, "execution_locked_symbols", ()))),
        )
        for entry in self.decisions[time]:
            original = self.snapshots[entry]
            proposed = MappingProxyType(dict(zip(original.symbol, original.weight, strict=True)))
            policy = self.decision_policy
            if policy is None:
                raise ValueError("decision policy unavailable")
            weights = policy(state, proposed)
            if weights is None:
                self.policy_snapshots[entry] = None
                continue
            if not isinstance(weights, Mapping) or any(
                not isinstance(symbol, str) or not symbol.strip() for symbol in weights
            ):
                raise ValueError("policy weights require nonempty symbol keys")
            snapshot = pd.DataFrame(
                [
                    {"decision_time": time, "entry_time": entry, "symbol": symbol, "weight": weight}
                    for symbol, weight in weights.items()
                ],
                columns=["decision_time", "entry_time", "symbol", "weight"],
            )
            _validate_target_weights(snapshot)
            self.policy_snapshots[entry] = snapshot

    def rebalance(self, time):
        snapshot = self.snapshots[time]
        if self.decision_policy is not None:
            snapshot = self.policy_snapshots[time]
            if snapshot is None:
                return
        for order in self.orders:
            if order["status"] == "pending":
                order.update(status="cancelled", reason="superseded")
        weights = dict(zip(snapshot.symbol, snapshot.weight, strict=False))
        cr, sr = self.receivables()
        nav = self.cash + self.value() + cr + sr
        for symbol in sorted(set(weights) | set(self.holdings)):
            if symbol in getattr(self, "execution_locked_symbols", ()):
                continue
            weight = weights.get(symbol, 0)
            mark = self.marks.get(symbol)
            blocked = symbol in self.valuation_state
            if blocked or (weight and mark is None):
                self.orders.append(
                    {
                        "order_id": len(self.orders),
                        "symbol": symbol,
                        "entry_time": time,
                        "decision_time": self.snapshots[time].decision_time.iloc[0],
                        "reference_price": mark,
                        "reference_basis": self.mark_basis.get(symbol, "raw"),
                        "reference_time": self.mark_times.get(symbol),
                        "reference_source_time": self.mark_source_times.get(symbol),
                        "side": "buy",
                        "quantity": 0,
                        "filled_quantity": 0,
                        "executed_notional": 0.0,
                        "commission_paid": 0.0,
                        "tax_paid": 0.0,
                        "status": "expired",
                        "reason": "nontrading_valuation" if blocked else "missing_mark",
                        "deadline": time,
                    }
                )
                continue
            target = (
                math.floor(nav * weight / mark / self.config.lot_size) * self.config.lot_size
                if weight
                else 0
            )
            delta = target - self.stock_exposure(symbol)
            if not delta:
                continue
            self.orders.append(
                {
                    "order_id": len(self.orders),
                    "symbol": symbol,
                    "entry_time": time,
                    "decision_time": self.snapshots[time].decision_time.iloc[0],
                    "reference_price": mark,
                    "reference_basis": self.mark_basis.get(symbol, "raw"),
                    "reference_time": self.mark_times.get(symbol),
                    "reference_source_time": self.mark_source_times.get(symbol),
                    "side": "buy" if delta > 0 else "sell",
                    "quantity": abs(delta),
                    "filled_quantity": 0,
                    "executed_notional": 0.0,
                    "commission_paid": 0.0,
                    "tax_paid": 0.0,
                    "status": "pending",
                    "reason": "no_eligible_bar",
                    "deadline": time + pd.Timedelta(minutes=self.config.execution_minutes),
                }
            )
        self.pending = [o for o in self.orders if o["status"] == "pending"]

    def sell_quantity(self, order, symbol, quantity, available, cap):
        holding = self.holdings.get(symbol, 0)
        sellable = holding - self.bought.get(symbol, 0)
        remaining = order["quantity"] - order["filled_quantity"]
        integer_holding = math.floor(holding)
        if (
            math.isclose(remaining, holding)
            and sellable >= integer_holding
            and min(available, cap) >= integer_holding
        ):
            return integer_holding
        return math.floor(quantity / self.config.lot_size) * self.config.lot_size

    def released_quantity(self, order, interval_start):
        elapsed = (
            interval_start - order["entry_time"]
        ).total_seconds() / 60 - self.config.latency_minutes
        spacing = self.config.execution_minutes / self.config.release_slices
        released = sum(elapsed > i * spacing for i in range(self.config.release_slices))
        available = (
            math.floor(
                order["quantity"] * released / self.config.release_slices / self.config.lot_size
            )
            * self.config.lot_size
            - order["filled_quantity"]
        )
        if order["side"] == "sell" and released == self.config.release_slices:
            available = math.floor(order["quantity"] - order["filled_quantity"])
        return available

    def incremental_fee(self, order, gross):
        if gross <= 0:
            return 0.0, 0.0
        tax_rate = self.config.sell_tax_bp / 10000 if order["side"] == "sell" else 0.0
        combined_rate = (
            self.config.buy_fee_bp if order["side"] == "buy" else self.config.sell_fee_bp
        ) / 10000
        total_commission = max(
            self.config.commission_minimum_cny,
            (order["executed_notional"] + gross) * (combined_rate - tax_rate),
        )
        return max(0.0, total_commission - order["commission_paid"]), gross * tax_rate

    def affordable_buy(self, order, quantity, price, time):
        low, high = 0, math.floor(quantity / self.config.lot_size)
        while low < high:
            middle = (low + high + 1) // 2
            shares = middle * self.config.lot_size
            affected = price
            if self.impact_model is not None:
                affected += self.impact_model.preview(order["symbol"], time.timestamp(), shares)
            gross = shares * affected
            commission, tax = self.incremental_fee(order, gross)
            if gross + commission + tax <= self.cash:
                low = middle
            else:
                high = middle - 1
        return low * self.config.lot_size

    def bar_block_reason(self, order, bar):
        reason = None
        if not bar.tradable or bar.volume == 0:
            reason = "not_tradable"
        elif order["side"] == "buy" and bar.high >= bar.up_limit:
            reason = "up_limit_touch"
        elif order["side"] == "sell" and bar.low <= bar.down_limit:
            reason = "down_limit_touch"
        return reason

    def impacted_price(self, symbol, time, signed, price):
        if self.impact_model is None:
            return price
        return price + self.impact_model.preview(symbol, time.timestamp(), signed)

    def fill_order(self, order, bar, time, cap):
        symbol = bar.symbol
        available = self.released_quantity(order, bar.interval_start)
        if available <= 0:
            return cap
        reason = self.bar_block_reason(order, bar)
        if reason:
            order["reason"] = reason
            return cap
        price = min(bar.high, max(bar.low, bar.amount / bar.volume))
        quantity = min(available, cap)
        if order["side"] == "buy":
            quantity = self.affordable_buy(order, quantity, price, time)
            order["reason"] = "cash_or_participation"
        else:
            quantity = min(quantity, self.holdings.get(symbol, 0) - self.bought.get(symbol, 0))
            quantity = self.sell_quantity(order, symbol, quantity, available, cap)
            order["reason"] = (
                "t_plus_one"
                if self.holdings.get(symbol, 0) == self.bought.get(symbol, 0)
                else "participation"
            )
        if quantity <= 0:
            return cap
        signed = quantity if order["side"] == "buy" else -quantity
        price = self.impacted_price(symbol, time, signed, price)
        if self.impact_model is not None and not bar.down_limit < price < bar.up_limit:
            order["reason"] = "impact_price_limit"
            return cap
        gross = quantity * price
        commission, tax = self.incremental_fee(order, gross)
        fee = commission + tax
        if order["side"] == "sell" and fee > self.cash + gross:
            order["reason"] = "fee_cash"
            return cap
        if self.impact_model is not None:
            self.impact_model.execute(symbol, time.timestamp(), signed)
        order["executed_notional"] += gross
        order["commission_paid"] += commission
        order["tax_paid"] += tax
        direction = 1 if order["side"] == "buy" else -1
        self.cash -= direction * gross + fee
        self.holdings[symbol] = self.holdings.get(symbol, 0) + direction * quantity
        if direction == 1:
            self.bought[symbol] = self.bought.get(symbol, 0) + quantity
        cap -= quantity
        self.costs += fee
        order["filled_quantity"] += quantity
        order["reason"] = "partial_fill"
        if order["filled_quantity"] == order["quantity"]:
            order.update(status="filled", reason="filled")
        self.fills.append(
            {
                "order_id": order["order_id"],
                "time": time,
                "symbol": symbol,
                "side": order["side"],
                "quantity": quantity,
                "price": price,
                "gross_amount": gross,
                "transaction_cost": fee,
                "commission": commission,
                "sell_tax": tax,
                "cash_after": self.cash,
            }
        )
        return cap

    def process_bars(self, time):
        observed = {b.symbol: b for b in self.grouped[time].itertuples()}
        self.clipped_vwap_bars += sum(
            b.volume > 0 and not b.low <= b.amount / b.volume <= b.high for b in observed.values()
        )
        capacities = {
            s: math.floor(b.volume * self.config.participation_rate / self.config.lot_size)
            * self.config.lot_size
            for s, b in observed.items()
        }
        for order in sorted(self.pending, key=lambda o: (o["side"] == "buy", o["order_id"])):
            symbol = order["symbol"]
            if (
                symbol not in observed
                or symbol in getattr(self, "bar_execution_locked_symbols", ())
                or order["status"] != "pending"
                or time > order["deadline"]
            ):
                continue
            capacities[symbol] = self.fill_order(order, observed[symbol], time, capacities[symbol])
        for symbol, bar in observed.items():
            if symbol in self.valuation_state:
                continue
            self.marks[symbol] = bar.close
            self.mark_days[symbol] = time.date()
            self.mark_times[symbol] = time
            self.mark_source_times[symbol] = getattr(bar, "mark_source_time", time)
            self.mark_basis[symbol] = getattr(bar, "mark_basis", "raw")

    def expire_orders(self, time):
        for order in self.pending:
            if order["status"] == "pending" and time > order["deadline"]:
                order["status"] = "expired"

    def advance_account(self, time):
        day = time.date()
        if day != self.current_day:
            if self.day_has_events:
                self.close_day()
            self.current_day = day
            self.day_has_events = False
            self.bought = {}
            self.open_day(day)
        self.current_time = time
        self.apply_valuations(time)
        apply_capital_flows(self, time)
        self.expire_orders(time)

    def run(self):
        for time in self.times:
            self.advance_account(time)
            if (
                time in self.grouped
                or time in self.snapshots
                or time in self.scheduled_valuations
                or time in self.scheduled_capital_flows
            ):
                self.day_has_events = True
            if self.decision_policy is not None and time in self.decisions:
                self.decide(time)
            if time in self.snapshots:
                self.rebalance(time)
            if time in self.grouped:
                self.process_bars(time)
        return self.finish()

    def finish(self):
        if self.day_has_events:
            self.close_day()
        for order in self.orders:
            if order["status"] == "pending":
                order["status"] = "expired"
        return MinuteExecutionResult(
            pd.DataFrame(self.daily),
            pd.DataFrame(self.orders),
            pd.DataFrame(
                self.fills,
                columns=[
                    "order_id",
                    "time",
                    "symbol",
                    "side",
                    "quantity",
                    "price",
                    "gross_amount",
                    "transaction_cost",
                    "commission",
                    "sell_tax",
                    "cash_after",
                ],
            ),
            {
                "initial_cash": self.config.initial_cash,
                "result_semantics": "execution_ledger_daily_nav",
                "account_feedback": self.decision_policy is not None,
                "account_delivery": "synchronous_no_report_delay",
                "cancellation": "synchronous_at_superseding_entry",
                "impact_checkpoint": self.impact_model.checkpoint() if self.impact_model else None,
                "impact_calibration": "uncalibrated_stress_only" if self.impact_model else "none",
                "valuation_basis": "external_raw_marks_excludes_own_impact",
                "strategy_market_basis": "external_raw_marks_excludes_own_impact",
                "valuation_event_count": len(self.valuation_ledger),
                "ignored_future_event_ids": self.ignored_future_event_ids,
                "valuation_event_window": "prewindow_at_first_instant_future_ignored",
                "nontrading_valuation_symbols": sorted(self.valuation_state),
                "commission_minimum_cny": self.config.commission_minimum_cny,
                "sell_tax_bp": self.config.sell_tax_bp,
                "commission_minimum_basis": "once_per_parent_order_across_partial_fills",
                "buy_fee_bp": self.config.buy_fee_bp,
                "sell_fee_bp": self.config.sell_fee_bp,
                "transaction_cost": self.costs,
                "price_proxy": "bounded_bar_vwap",
                "duration_basis": "wall_clock_minutes",
                "bar_eligibility": "interval_start_strictly_after_release_plus_latency",
                "default_bar_interval": "one_minute_ending_at_time",
                "ex_reference_basis": "(previous_raw_mark-gross_cash)/(1+stock_ratio)",
                "clipped_vwap_bars": self.clipped_vwap_bars,
                "fractional_positions": {
                    s: q - math.floor(q) for s, q in self.holdings.items() if q != math.floor(q)
                },
            },
            pd.DataFrame(self.holdings_ledger, columns=["date", "symbol", "quantity"]),
            pd.DataFrame(self.valuation_ledger, columns=VALUATION_LEDGER_COLUMNS),
            pd.DataFrame(self.capital_flow_ledger, columns=CAPITAL_FLOW_COLUMNS),
        )
