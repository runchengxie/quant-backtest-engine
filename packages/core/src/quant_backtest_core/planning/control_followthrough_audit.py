"""Read-only moving-price reconciliation and descriptive failure flags."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from .owner_control_audit import _fills_and_orders, _near, _participation, _require


def price_decomposition(
    fills: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    quantity: int,
    benchmark: float,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    """Decompose a sell-only exit against observed raw marks, including residuals."""
    _require(type(quantity) is int and quantity > 0, "positive target required")
    _require(np.isfinite(benchmark) and benchmark > 0 and end >= start, "invalid benchmark/horizon")
    _require(not bars.time.duplicated().any(), "duplicate raw quote")
    _require(bool(np.isfinite(bars.close).all() and bars.close.gt(0).all()), "invalid raw quote")
    _require(bool(fills.time.between(start, end).all()), "fill outside exposure horizon")
    _require(
        bool(np.isfinite(fills[["quantity", "price", "transaction_cost"]]).all().all()),
        "invalid fill",
    )
    _require(
        bool(fills.quantity.gt(0).all() and fills.quantity.eq(fills.quantity.astype(int)).all()),
        "invalid quantity",
    )
    _require(
        bool(fills.transaction_cost.ge(0).all() and fills.price.gt(0).all()), "invalid fill amounts"
    )
    raw = bars.set_index("time").close.reindex(fills.time)
    _require(bool(raw.notna().all()), "fill missing exact raw quote")
    observed = bars.loc[bars.time.le(end)].sort_values("time")
    _require(not observed.empty, "terminal raw quote missing")
    terminal = float(observed.iloc[-1].close)
    q = float(fills.quantity.sum())
    _require(q <= quantity, "oversold target")
    drift = float(np.sum(fills.quantity.to_numpy() * (benchmark - raw.to_numpy())))
    deviation = float(np.sum(fills.quantity.to_numpy() * (raw.to_numpy() - fills.price.to_numpy())))
    fees = float(fills.transaction_cost.sum())
    residual_mark = (quantity - q) * (benchmark - terminal)
    exposure = squared = 0.0
    inventory, previous = float(quantity), start
    for time, part in fills.groupby("time", sort=True):
        minutes = (time - previous).total_seconds() / 60
        exposure += inventory * minutes
        squared += inventory**2 * minutes
        inventory -= float(part.quantity.sum())
        previous = time
    minutes = (end - previous).total_seconds() / 60
    exposure += inventory * minutes
    squared += inventory**2 * minutes
    return dict(
        price_drift_cny=drift,
        execution_deviation_cny=deviation,
        exit_fees_cny=fees,
        residual_mark_shortfall_cny=residual_mark,
        full_target_marked_shortfall_cny=drift + deviation + fees + residual_mark,
        inventory_share_minutes=exposure,
        inventory_squared_share_minutes=squared,
        terminal_raw_mark=terminal,
    )


def audit_study(case: Any, result: Any, diagnostics: dict[str, Any]) -> dict[str, Any]:
    """Audit owner tables with their actual dated last raw mark, never forecast price."""
    from .control_followthrough import study_inputs

    targets, bars, config = study_inputs(case)
    _fills_and_orders(result, config)
    _participation(result, bars, config)
    _require(not result.daily.empty, "daily owner result missing")
    for row in result.daily.itertuples():
        prefix = result.fills.loc[result.fills.time.dt.date.le(row.date)]
        held = result.holdings.loc[result.holdings.date.eq(row.date)]
        buys = prefix.loc[prefix.side.eq("buy")]
        sells = prefix.loc[prefix.side.eq("sell")]
        inventory = float(buys.quantity.sum() - sells.quantity.sum())
        _require(inventory >= 0, "owner oversold")
        _near(held.quantity.sum(), inventory, "owner holding mismatch")
        observed = bars.loc[bars.time.dt.date.le(row.date)].sort_values("time")
        _require(not observed.empty, "daily raw mark missing")
        _near(
            row.positions_value,
            inventory * float(observed.iloc[-1].close),
            "owner raw mark mismatch",
        )
        _near(row.transaction_cost, prefix.transaction_cost.sum(), "owner cumulative fees mismatch")
        _near(
            row.cash,
            config.initial_cash
            + sells.gross_amount.sum()
            - buys.gross_amount.sum()
            - prefix.transaction_cost.sum(),
            "owner cash mismatch",
        )
        _near(row.nav, row.cash + row.positions_value, "owner NAV mismatch")
        _require(
            row.cash_receivable == 0 and row.stock_receivable_value == 0, "unexpected receivable"
        )
    exit_start = targets.entry_time.iloc[1]
    end = targets.entry_time.iloc[-1] + pd.Timedelta(minutes=2)
    seed = result.fills.loc[result.fills.time.lt(exit_start)]
    exit_fills = result.fills.loc[result.fills.time.ge(exit_start)]
    _require(
        bool(seed.side.eq("buy").all() and exit_fills.side.eq("sell").all()),
        "invalid seed/exit sides",
    )
    _near(seed.quantity.sum(), case.base.quantity, "seed not established")
    q = float(exit_fills.quantity.sum())
    residual = case.base.quantity - q
    v: dict[str, Any] = price_decomposition(
        exit_fills, bars, quantity=case.base.quantity, benchmark=10.0, start=exit_start, end=end
    )
    eligible = pd.Series(False, index=bars.index)
    for entry in targets.entry_time.iloc[1:]:
        eligible |= bars.interval_start.gt(
            entry + pd.Timedelta(minutes=config.latency_minutes)
        ) & bars.time.le(entry + pd.Timedelta(minutes=2))
    capacity = int(np.floor(bars.loc[eligible, "volume"] * config.participation_rate).sum())
    trace = diagnostics["policy_trace"]
    failures = sum(r["action"] == "planning_failure" for r in trace)
    waits = sum(r["action"] == "wait_pending" for r in trace)
    reports = sum(r["undelivered_reports"] > 0 for r in diagnostics["delivery_trace"])
    v.update(
        exit_quantity=q,
        residual_quantity=residual,
        filled_fraction=q / case.base.quantity,
        completed=residual == 0,
        rankable=residual == 0
        and result.summary["financial_reports_pending"] == 0
        and not result.orders.status.eq("pending").any(),
        planning_failure_decisions=failures,
        wait_pending_decisions=waits,
        report_gate_decisions=reports,
        realized_clock_capacity=capacity,
        insufficient_realized_clock_capacity=capacity < case.base.quantity,
        planning_failure_observed=failures > 0,
        feedback_wait_observed=waits > 0,
        fixed_submission_slots_lost=sum(
            r["action"] == "wait_pending"
            and (
                case.base.policy in ("twap", "open_loop")
                or (case.base.policy == "immediate" and r["slot"] == 0)
            )
            for r in trace
        ),
        unfilled_requested_quantity=float(
            result.orders.loc[result.orders.side.eq("sell"), "quantity"].sum() - q
        ),
        owner_final_cash=float(result.daily.iloc[-1].cash),
        owner_final_nav=float(result.daily.iloc[-1].nav),
    )
    return v
