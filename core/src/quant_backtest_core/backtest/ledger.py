"""Engine-neutral ledger data and reconciliation; no execution implementation."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class UnifiedLedger:
    """Roadmap-defined 8-field reconciled ledger.

    Produced by :func:`to_unified_ledger` so the independent execution-sim
    engine can feed the shared daily-ledger contract without changing the
    historical ``not_available`` semantics of callers that do not opt in.
    """

    targets: pd.DataFrame
    orders: pd.DataFrame
    fills: pd.DataFrame
    daily_positions: pd.DataFrame
    daily_cash: pd.DataFrame
    daily_nav: pd.DataFrame
    cost_breakdown: pd.DataFrame
    turnover_breakdown: pd.DataFrame


def _require_columns(frame: pd.DataFrame, columns: set[str], *, label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing columns: " + ", ".join(missing))


def validate_ledger_frames(ledger: UnifiedLedger) -> None:
    for name in (
        "targets",
        "orders",
        "fills",
        "daily_positions",
        "daily_cash",
        "daily_nav",
        "cost_breakdown",
        "turnover_breakdown",
    ):
        if not isinstance(getattr(ledger, name, None), pd.DataFrame):
            raise TypeError(f"UnifiedLedger.{name} must be a pandas DataFrame")


def reconcile_unified_ledger(
    ledger: UnifiedLedger,
    *,
    tolerance: float = 1e-8,
) -> dict[str, float | int | str]:
    validate_ledger_frames(ledger)
    _require_columns(
        ledger.daily_positions,
        {"trade_date", "positions_value"},
        label="daily_positions",
    )
    _require_columns(ledger.daily_cash, {"trade_date", "cash"}, label="daily_cash")
    _require_columns(ledger.daily_nav, {"trade_date", "nav"}, label="daily_nav")
    if ledger.daily_nav.empty:
        raise ValueError("daily_nav must contain at least one row for reconciliation")

    positions = ledger.daily_positions[["trade_date", "positions_value"]].copy()
    cash = ledger.daily_cash[["trade_date", "cash"]].copy()
    nav = ledger.daily_nav[["trade_date", "nav"]].copy()
    for frame in (positions, cash, nav):
        frame["trade_date"] = frame["trade_date"].astype(str)
        if frame["trade_date"].duplicated().any():
            raise ValueError("daily ledger trade_date values must be unique")

    merged = nav.merge(cash, on="trade_date", how="outer", validate="one_to_one").merge(
        positions,
        on="trade_date",
        how="outer",
        validate="one_to_one",
    )
    if merged[["nav", "cash", "positions_value"]].isna().any().any():
        raise ValueError("daily ledger date coverage must match across nav, cash and positions")

    for column in ("nav", "cash", "positions_value"):
        merged[column] = pd.to_numeric(merged[column], errors="coerce")
    if merged[["nav", "cash", "positions_value"]].isna().any().any():
        raise ValueError("daily ledger accounting columns must be numeric")

    expected = merged["cash"] + merged["positions_value"]
    errors = (merged["nav"] - expected).abs()
    scale = pd.concat([merged["nav"].abs(), expected.abs()], axis=1).max(axis=1).clip(lower=1.0)
    if (errors > float(tolerance) * scale).any():
        raise ValueError("daily ledger must satisfy nav = cash + positions_value")
    return {
        "status": "passed",
        "rows": len(merged),
        "max_abs_error": float(errors.max()),
        "tolerance": float(tolerance),
    }
