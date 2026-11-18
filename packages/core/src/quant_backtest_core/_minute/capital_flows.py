# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/_portfolio/capital_flows.py
# Original SHA256: 403eb8714b07141609a879b276f3b1aa171838a088e111c2a3f1095f26051664
"""External capital accounting shared by synchronous and recoverable minute owners."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

import pandas as pd

from .valuation_events import ValuationEvent

CAPITAL_FLOW_COLUMNS = (
    "time",
    "event_id",
    "available_time",
    "effective_time",
    "source",
    "amount",
    "cash_before",
    "cash_after",
    "nav_before",
    "nav_after",
)


@dataclass(frozen=True)
class CapitalFlow:
    """Signed external cash at an aware effective clock, available no later.

    Positive is a deposit; negative is a cash-only withdrawal. A withdrawal may
    not overdraw cash. Same-clock events apply in event_id order before decisions.
    """

    event_id: str
    available_time: str | datetime | pd.Timestamp
    effective_time: str | datetime | pd.Timestamp
    amount: float
    source: str

    def __post_init__(self):
        # Reuse the established aware-clock and normalized-string contract.
        validated = ValuationEvent(
            self.event_id,
            "capital",
            self.effective_time,
            self.available_time,
            abs(float(self.amount)),
            "external_capital",
            self.source,
        )
        if float(self.amount) == 0:
            raise ValueError("capital flow amount must be nonzero")
        object.__setattr__(self, "amount", float(self.amount))
        object.__setattr__(self, "effective_time", validated.effective_time)
        object.__setattr__(self, "available_time", validated.available_time)


def initialize_capital(sim, flows):
    sim.capital_flows = tuple(flows)
    seen = set()
    for flow in sim.capital_flows:
        if type(flow) is not CapitalFlow:
            raise ValueError("capital_flows must contain exact CapitalFlow events")
        if flow.event_id in seen:
            raise ValueError("duplicate capital flow event_id")
        seen.add(flow.event_id)
    sim.capital_flow_ledger = []
    sim.applied_capital_flow_ids = set()
    sim.cumulative_capital_flow = 0.0
    sim.return_factor = 1.0
    sim.return_anchor = float(sim.config.initial_cash)
    sim.scheduled_capital_flows = {}
    if not sim.capital_flows:
        return
    if not sim.times:
        raise ValueError("capital flows require a nonempty simulation window")
    first, last = sim.times[0], sim.times[-1]
    for flow in sorted(sim.capital_flows, key=lambda f: (f.effective_time, f.event_id)):
        if not first <= flow.effective_time <= last:
            raise ValueError("capital flow effective_time must be within simulation window")
        time = pd.Timestamp(flow.effective_time).tz_convert(first.tz)
        sim.scheduled_capital_flows.setdefault(time, []).append(flow)
    sim.times = sorted(set(sim.times) | set(sim.scheduled_capital_flows))


def marked_wealth(sim):
    symbols = {s for s, q in sim.holdings.items() if q} | {
        r["symbol"] for r in sim.rights.values() if r["ex"] and r["stock"]
    }
    if any(s not in sim.marks or sim.stale_mark(s) for s in symbols):
        return float("nan")
    cash_right, stock_right = sim.receivables()
    return sim.cash + sim.value() + cash_right + stock_right


def apply_capital_flows(sim, time):
    for flow in sim.scheduled_capital_flows.get(time, ()):
        if flow.event_id in sim.applied_capital_flow_ids:
            continue
        if not isfinite(sim.cash + flow.amount):
            raise ValueError("capital flow must leave finite cash")
        if sim.cash + flow.amount < 0:
            raise ValueError("capital withdrawal exceeds available economic cash")
        before = marked_wealth(sim)
        cash_before = sim.cash
        sim.return_factor *= (
            before / sim.return_anchor if sim.return_anchor > 0 and before > 0 else float("nan")
        )
        sim.return_anchor = before + flow.amount
        if sim.return_anchor <= 0:
            sim.return_factor = float("nan")
        sim.cash += flow.amount
        sim.cumulative_capital_flow += flow.amount
        sim.capital_flow_ledger.append(
            {
                "time": time,
                "event_id": flow.event_id,
                "available_time": flow.available_time,
                "effective_time": flow.effective_time,
                "source": flow.source,
                "amount": flow.amount,
                "cash_before": cash_before,
                "cash_after": sim.cash,
                "nav_before": before,
                "nav_after": before + flow.amount,
            }
        )
        sim.applied_capital_flow_ids.add(flow.event_id)


def capital_daily(sim, row):
    if not sim.capital_flows:
        return
    row.update(
        capital_flow=sum(
            f["amount"] for f in sim.capital_flow_ledger if f["time"].date() == sim.current_day
        ),
        cumulative_capital_flow=sim.cumulative_capital_flow,
        pnl=row["nav"] - sim.config.initial_cash - sim.cumulative_capital_flow,
        cumulative_return=(
            sim.return_factor * row["nav"] / sim.return_anchor - 1
            if sim.return_anchor > 0 and row["nav"] > 0
            else float("nan")
        ),
    )
