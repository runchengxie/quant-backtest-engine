# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/backtest/minute_session.py
# Original SHA256: 0872227f551639c1b75ef84119691e4c92171c7c3af16ff55a95c45452ee7039
"""Recoverable bar execution with conservative delayed financial snapshots.

Uses the existing minute matcher and ledger. No queue model or network cancel
latency is added. Quotes remain external and undelivered reports prohibit new
orders, regardless of policy behavior. Financial tapes reuse the synchronous
owner, with delayed receivables and explicit external capital accounting.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from types import MappingProxyType
from typing import Any

import pandas as pd

from quant_backtest_core._minute.capital_flows import CapitalFlow, initialize_capital
from quant_backtest_core._minute.corporate_actions import CorporateAction
from quant_backtest_core._minute.minute_execution import _MinuteSimulation
from quant_backtest_core._minute.valuation_events import ValuationEvent

from ._minute_checkpoint import _FIELDS, _binding, _digest, _unwire, _wire
from .impact import LinearImpact
from .quantity_locks import QuantityLock


class MinuteSession:
    """Policy must implement checkpoint(); caller restores its own policy type.

    Checkpoints contain financial state and bind exact inputs, configuration and
    loaded source. Digests detect accidental modification, not malicious authors.
    Deliveries are a causal prefix. Economic fills and T+1 remain owner behavior.
    """

    def __init__(
        self,
        targets,
        bars,
        config,
        *,
        policy,
        report_delay_seconds=0,
        impact=None,
        quantity_locks=(),
        corporate_actions=(),
        valuation_events=(),
        capital_flows=(),
    ):
        if impact is not None and type(impact) is not LinearImpact:
            raise ValueError("recoverable session requires exact LinearImpact type")
        if not math.isfinite(report_delay_seconds) or report_delay_seconds < 0:
            raise ValueError("finite nonnegative report delay required")
        self.quantity_locks = tuple(quantity_locks)
        if any(type(lock) is not QuantityLock for lock in self.quantity_locks):
            raise ValueError("exact QuantityLock notices required")
        self.targets, self.bars, self.config = targets.copy(), bars.copy(), config
        self.policy = policy
        self.delay = report_delay_seconds
        self.cursor, self.finished, self.failed = 0, False, False
        self.queue = []
        self.corporate_actions = tuple(corporate_actions)
        self.valuation_events = tuple(valuation_events)
        self.capital_flows = tuple(capital_flows)
        self.tapes = {
            "corporate_actions": self.corporate_actions,
            "valuation_events": self.valuation_events,
            "capital_flows": self.capital_flows,
        }
        for name, cls in (
            ("corporate_actions", CorporateAction),
            ("valuation_events", ValuationEvent),
            ("capital_flows", CapitalFlow),
        ):
            if any(type(event) is not cls for event in self.tapes[name]):
                raise ValueError(f"{name} requires exact {cls.__name__} events")
        self.simulation = _MinuteSimulation(
            self.targets, self.bars, config, self.corporate_actions, self.valuation_events
        )
        self.binding = _binding(targets, bars, config, policy, self.quantity_locks, self.tapes)
        self.simulation.decision_policy = self._decide
        self.simulation.impact_model = impact
        self.simulation.times = sorted(set(self.simulation.times) | set(self.simulation.decisions))
        self.simulation.ignored_future_event_ids = []
        self.simulation.scheduled_valuations = self.simulation.schedule_valuations()
        self.simulation.times = sorted(
            set(self.simulation.times) | set(self.simulation.scheduled_valuations)
        )
        initialize_capital(self.simulation, self.capital_flows)
        self._schedule_locks()
        self.delivered: dict[str, Any] = {
            "cash": config.initial_cash,
            "holdings": {},
            "pending_orders": (),
            "rights": {},
        }
        self.trace = []

    def _schedule_locks(self):
        sim = self.simulation
        if not sim.times or not self.quantity_locks:
            return
        first, last = sim.times[0], sim.times[-1]
        events = set(sim.times)
        for lock in self.quantity_locks:
            for ns in (max(lock.available_ns, lock.start_ns), lock.end_ns + 1):
                time = pd.Timestamp(ns, tz="UTC").tz_convert(first.tz)
                if first <= time <= last:
                    events.add(time)
        sim.times = sorted(events)

    def _apply_locks(self, time):
        sim = self.simulation
        now = int(time.value)
        active = {
            symbol
            for lock in self.quantity_locks
            if lock.overlaps(now, now)
            for symbol in lock.symbols
        }
        sim.execution_locked_symbols = tuple(sorted(active))
        for order in sim.pending:
            if order["status"] == "pending" and order["symbol"] in active:
                order.update(status="cancelled", reason="quantity_lock")
        # A bar spanning a lock boundary cannot identify an unlocked fill time.
        # Conservatively prohibit that entire bar, without moving its clock.
        sim.bar_execution_locked_symbols = tuple(
            sorted(
                {
                    bar.symbol
                    for bar in sim.grouped.get(time, pd.DataFrame()).itertuples()
                    for lock in self.quantity_locks
                    if bar.symbol in lock.symbols
                    and lock.overlaps(int(bar.interval_start.value), now)
                }
            )
        )

    def _decide(self, state, proposed):
        pending = self.delivered["pending_orders"]
        if self.queue:
            pending = (
                *pending,
                {"status": "undelivered_financial_report", "remaining_quantity": 0},
            )
        holdings = self.delivered["holdings"]
        rights = self.delivered["rights"]
        cr = sum(r["cash"] for r in rights.values() if r["ex"])
        sr = sum(
            r["stock"] * state.marks.get(r["symbol"], float("nan"))
            for r in rights.values()
            if r["ex"] and r["stock"]
        )
        nav = (
            self.delivered["cash"]
            + cr
            + sr
            + sum(q * state.marks.get(s, float("nan")) for s, q in holdings.items() if q)
        )
        visible = replace(
            state,
            cash=self.delivered["cash"],
            nav=nav,
            cash_receivable=cr,
            stock_receivable_value=sr,
            holdings=MappingProxyType(dict(holdings)),
            quantity_locks=tuple(
                lock for lock in self.quantity_locks if lock.available_ns <= state.time.value
            ),
            pending_orders=tuple(MappingProxyType(dict(order)) for order in pending),
        )
        weights = self.policy(visible, proposed)
        self.trace.append(
            {
                "time": state.time.isoformat(),
                "visible_cash": visible.cash,
                "visible_holdings": dict(visible.holdings),
                "undelivered_reports": len(self.queue),
                "action": "wait_reports" if self.queue else "policy",
            }
        )
        return None if self.queue else weights

    def _snapshot(self):
        sim = self.simulation
        return {
            "cash": sim.cash,
            "holdings": dict(sim.holdings),
            "rights": {key: dict(right) for key, right in sim.rights.items()},
            "pending_orders": tuple(
                {**o, "remaining_quantity": o["quantity"] - o["filled_quantity"]}
                for o in sim.pending
                if o["status"] == "pending"
            ),
        }

    def _deliver(self, time):
        while self.queue and self.queue[0][0] <= time:
            _, self.delivered = self.queue.pop(0)

    def step(self):
        if self.finished:
            raise ValueError("session already finished")
        if self.failed:
            raise ValueError("failed session: reconstruct from last successful checkpoint")
        try:
            return self._step()
        except Exception:
            self.failed = True
            raise

    def _step(self):
        sim = self.simulation
        if self.cursor == len(sim.times):
            return False
        time = sim.times[self.cursor]
        before = self._snapshot()
        sim.advance_account(time)
        self._apply_locks(time)
        self._deliver(time)
        after_account = self._snapshot()
        if self.delay and before != after_account:
            self.queue.append((time + pd.Timedelta(seconds=self.delay), after_account))
        before = after_account
        if not self.delay:
            self.delivered = self._snapshot()
        if (
            time in sim.grouped
            or time in sim.snapshots
            or time in sim.scheduled_valuations
            or time in sim.scheduled_capital_flows
        ):
            sim.day_has_events = True
        if time in sim.decisions:
            sim.decide(time)
        if time in sim.snapshots:
            if self.queue:
                sim.policy_snapshots[time] = None
            sim.rebalance(time)
        if time in sim.grouped:
            sim.process_bars(time)
        after = self._snapshot()
        if before != after:
            self.queue.append((time + pd.Timedelta(seconds=self.delay), after))
        self._deliver(time)
        self.cursor += 1
        return True

    def run(self):
        while self.step():
            pass
        result = self.simulation.finish()
        self.finished = True
        result.summary.update(
            account_delivery="causal_prefix_delayed_snapshots",
            report_delay_seconds=self.delay,
            cancellation="synchronous_exchange_delayed_acknowledgement",
            financial_reports_pending=len(self.queue),
            quantity_lock_notices=len(self.quantity_locks),
        )
        return result

    def checkpoint(self):
        if self.failed:
            raise ValueError("failed session: reconstruct from last successful checkpoint")
        if self.finished:
            raise ValueError("cannot checkpoint a finished session")
        sim = self.simulation
        state = {key: getattr(sim, key) for key in _FIELDS}
        value = {
            "schema": "minute-session.v3",
            "tape_contract": "minute-financial-tapes.v1",
            "tapes": _wire(self.tapes),
            "binding": self.binding,
            "cursor": self.cursor,
            "delay": self.delay,
            "quantity_locks": [asdict(lock) for lock in self.quantity_locks],
            "policy": json.loads(json.dumps(self.policy.checkpoint(), allow_nan=False)),
            "impact": sim.impact_model.checkpoint() if sim.impact_model else None,
            "state": _wire(state),
            "delivery": _wire([self.delivered, self.queue, self.trace]),
        }
        return {**value, "digest": _digest(value)}

    @classmethod
    def restore(
        cls,
        targets,
        bars,
        config,
        checkpoint,
        *,
        policy,
        corporate_actions=None,
        valuation_events=None,
        capital_flows=None,
    ):
        value = dict(checkpoint)
        digest = value.pop("digest", None)
        if value.get("schema") != "minute-session.v3":
            raise ValueError(
                "unsupported checkpoint schema: restart from inputs or use original pinned sources"
            )
        if value.get("tape_contract") != "minute-financial-tapes.v1" or digest != _digest(value):
            raise ValueError("checkpoint integrity mismatch")
        tapes = _unwire(value["tapes"])
        expected = {
            "corporate_actions": corporate_actions,
            "valuation_events": valuation_events,
            "capital_flows": capital_flows,
        }
        for name, supplied in expected.items():
            if supplied is not None and _wire(tuple(supplied)) != _wire(tapes[name]):
                raise ValueError("checkpoint financial tape binding mismatch")
        result = cls(
            targets,
            bars,
            config,
            policy=policy,
            **tapes,
            report_delay_seconds=value["delay"],
            impact=LinearImpact.restore(value["impact"]) if value["impact"] else None,
            quantity_locks=tuple(
                QuantityLock(
                    available_ns=lock["available_ns"],
                    start_ns=lock["start_ns"],
                    end_ns=lock["end_ns"],
                    symbols=tuple(lock["symbols"]),
                    source_binding=lock["source_binding"],
                )
                for lock in value["quantity_locks"]
            ),
        )
        if (
            result.binding != value["binding"]
            or json.loads(json.dumps(policy.checkpoint(), allow_nan=False)) != value["policy"]
        ):
            raise ValueError("checkpoint source/input/policy binding mismatch")
        if type(value["cursor"]) is not int or not 0 <= value["cursor"] <= len(
            result.simulation.times
        ):
            raise ValueError("invalid checkpoint cursor")
        state = _unwire(value["state"])
        if set(state) != set(_FIELDS):
            raise ValueError("checkpoint state incomplete: restart from inputs or original sources")
        for key, item in state.items():
            if key not in _FIELDS:
                raise ValueError("invalid checkpoint field")
            setattr(result.simulation, key, item)
        result.simulation.pending = [
            o for o in result.simulation.orders if o["status"] == "pending"
        ]
        result.delivered, result.queue, result.trace = _unwire(value["delivery"])
        result.cursor = value["cursor"]
        return result
