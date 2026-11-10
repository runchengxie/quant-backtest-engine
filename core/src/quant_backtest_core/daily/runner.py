"""Explicit daily owner dispatch; no target selection, calendar lookup or fallback."""

from dataclasses import asdict, replace
from typing import Any

import numpy as np
import pandas as pd

from .contracts import DailyReplayRequest, DailySummaryEvidence, strict_date
from .execution import DetailedTradeFeeModel
from .execution_sim import (
    ExecutionAdjustedNavResult,
    ExecutionSimResult,
    simulate_capacity_execution,
    simulate_execution_adjusted_nav,
    simulate_ideal_daily_nav,
)
from .summary import summarize_execution


def validate_request(request: DailyReplayRequest) -> None:
    positions, pricing = request.positions, request.pricing
    if not request.config.enabled:
        raise ValueError("daily execution requires an enabled simulator")
    if request.calendar.timezone != "Asia/Shanghai":
        raise ValueError("daily owner audit dates require Asia/Shanghai")
    for frame, required in (
        (positions, {"rebalance_date", "entry_date", "symbol", "weight"}),
        (pricing, {"trade_date", "symbol", request.layout.price_col}),
    ):
        if missing := required - set(frame):
            raise ValueError(f"missing daily columns: {sorted(missing)}")
        if frame.empty:
            raise ValueError("positions and pricing must be nonempty")
        if (
            frame.symbol.isna().any()
            or not frame.symbol.map(lambda v: isinstance(v, str) and bool(v.strip())).all()
        ):
            raise ValueError("symbols must be nonempty strings")
    for column in ("rebalance_date", "entry_date"):
        for value in positions[column]:
            strict_date(value)
    dates = {strict_date(v) for v in pricing.trade_date}
    sessions = set(request.calendar.open_dates)
    if not dates <= sessions:
        raise ValueError("pricing dates outside supplied calendar")
    expected = {d for d in sessions if min(dates) <= d <= max(dates)}
    if dates != expected:
        raise ValueError("pricing must cover every supplied session in its horizon")
    if not set(positions.entry_date) <= dates:
        raise ValueError("every target entry needs supplied calendar and pricing coverage")
    if positions.duplicated(["rebalance_date", "symbol"]).any():
        raise ValueError("duplicate symbols in a decision")
    if pricing.duplicated(["trade_date", "symbol"]).any():
        raise ValueError("duplicate daily pricing rows")
    weights = pd.to_numeric(positions.weight, errors="coerce")
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("target weights must be finite nonnegative numbers")
    if weights.groupby(positions.rebalance_date).sum().gt(1.0 + 1e-9).any():
        raise ValueError("target weights exceed full investment")
    if "side" in positions and not positions.side.eq("long").all():
        raise ValueError("daily owner supports long-only targets")
    if positions.groupby("rebalance_date").entry_date.nunique().gt(1).any():
        raise ValueError("each decision requires one entry date")
    if positions[["rebalance_date", "entry_date"]].drop_duplicates().entry_date.duplicated().any():
        raise ValueError("multiple decisions cannot overwrite the same entry session")

    def local_day(ns: str | None) -> str:
        if ns is None:
            raise ValueError("required clock is unavailable")
        return (
            pd.Timestamp(int(ns), tz="UTC").tz_convert(request.calendar.timezone).date().isoformat()
        )

    for row in positions.itertuples():
        clock = request.decision_clocks[row.rebalance_date]
        if local_day(clock.information_ns) != row.rebalance_date:
            raise ValueError("information cutoff date must match rebalance date")
        if local_day(clock.entry_ns) != row.entry_date:
            raise ValueError("entry date falls outside its execution clock")
        timing = request.decision_timing.get(row.rebalance_date)
        if timing is not None and timing.execution_window_end_ns is not None:
            if row.entry_date > local_day(timing.execution_window_end_ns):
                raise ValueError("entry date falls outside its execution clock")
    valuations = [c.valuation_ns for c in request.decision_clocks.values()]
    if any(v is None for v in valuations):
        raise ValueError("daily replay requires explicit valuation horizon")
    if max(dates) > max(local_day(v) for v in valuations if v is not None):
        raise ValueError("pricing extends past final decision valuation")
    if request.mode == "capacity":
        for name, supported in (
            ("unfilled_buy_action", "keep_cash"),
            ("unfilled_sell_action", "keep_position"),
        ):
            if getattr(request.config, name) != supported:
                raise ValueError(f"capacity mode requires {name}={supported}")
        unsupported = [
            name
            for name in ("enforce_price_limits", "enforce_listing_status", "enforce_t1")
            if getattr(request.config, name)
        ]
        unsupported.extend(
            name
            for name in ("round_lot", "sell_round_lot")
            if getattr(request.config, name) is not None
        )
        if unsupported:
            raise ValueError(
                "capacity mode does not support "
                + ", ".join(unsupported)
                + "; disable unsupported controls"
            )
    if request.mode in {"adjusted", "sequenced"} and request.config.enforce_listing_status:
        raise ValueError(f"{request.mode} mode does not support enforce_listing_status")
    for enabled, rule_column in (
        (request.config.enforce_price_limits, request.config.limit_up_col),
        (request.config.enforce_price_limits, request.config.limit_down_col),
        (request.config.enforce_listing_status, request.config.listing_status_col),
    ):
        if enabled and (rule_column is None or pricing[rule_column].isna().any()):
            raise ValueError("enabled market rule contains unknown values")
    if request.mode in {"ideal", "capacity"} and request.corporate_actions:
        raise ValueError("corporate actions require adjusted or sequenced share ledger")
    if request.mode == "capacity" and request.fee_model is not None:
        raise ValueError("capacity diagnostic has no fee ledger")
    if request.mode == "ideal":
        if request.fee_model is not None and not isinstance(
            request.fee_model, DetailedTradeFeeModel
        ):
            raise ValueError("ideal path requires a detailed fixed fee model")
        if any(
            (
                request.config.enforce_t1,
                request.config.enforce_price_limits,
                request.config.enforce_listing_status,
                request.config.round_lot,
                request.config.sell_round_lot,
                request.layout.tradable_col,
                request.layout.buy_tradable_col,
                request.layout.sell_tradable_col,
            )
        ):
            raise ValueError("ideal path cannot enforce trading controls or market rules")


def run_daily(request: DailyReplayRequest) -> ExecutionAdjustedNavResult | ExecutionSimResult:
    validate_request(request)
    layout, config = request.layout, request.config
    kwargs: dict[str, Any] = dict(
        price_col=layout.price_col,
        limit_up_col=config.limit_up_col,
        limit_down_col=config.limit_down_col,
        listing_status_col=config.listing_status_col,
    )
    if request.mode == "ideal":
        result = simulate_ideal_daily_nav(
            request.positions,
            request.pricing,
            **kwargs,
            portfolio_value=config.portfolio_value,
            trade_fee_model=request.fee_model,
        )
    else:
        kwargs.update(
            tradable_col=layout.tradable_col,
            buy_tradable_col=layout.buy_tradable_col,
            sell_tradable_col=layout.sell_tradable_col,
        )
        if request.mode == "capacity":
            return simulate_capacity_execution(request.positions, request.pricing, config, **kwargs)
        result = simulate_execution_adjusted_nav(
            request.positions,
            request.pricing,
            config,
            **kwargs,
            trade_fee_model=request.fee_model,
            corporate_actions=request.legacy_corporate_actions(),
            price_basis=request.price_basis,
        )
    if result.summary.get("status") != "ok":
        raise ValueError(f"daily execution failed: {result.summary.get('status')}")
    # Conservative endpoint evidence: every target has a current finite positive
    # mark. A carried-forward owner NAV cannot establish an interval endpoint.
    table = request.pricing.pivot(index="trade_date", columns="symbol", values=layout.price_col)
    symbols = sorted(set(request.positions.symbol))
    marks = tuple(
        bool(np.isfinite(values).all() and (values > 0).all())
        for values in (
            pd.to_numeric(
                table.reindex(index=[pd.Timestamp(day).date().isoformat()], columns=symbols).iloc[
                    0
                ],
                errors="coerce",
            )
            for day in result.daily.trade_date
        )
    )
    # These fresh-run owners start with configured cash, no holdings or receivables;
    # there is no restoration or external-flow input in this neutral profile.
    initial_cash_complete = bool(np.isfinite(config.portfolio_value) and config.portfolio_value > 0)
    intervals = tuple(
        closing and (initial_cash_complete if index == 0 else marks[index - 1])
        for index, closing in enumerate(marks)
    )
    evidence = DailySummaryEvidence("available", "available", intervals, (True,) * len(marks))
    summary = dict(result.summary)
    summary["execution_summary"] = asdict(
        summarize_execution(result.daily, result.fills, evidence=evidence)
    )
    summary["audit_time_semantics"] = "legacy date labels; not observed intraday clocks"
    return replace(result, summary=summary)
