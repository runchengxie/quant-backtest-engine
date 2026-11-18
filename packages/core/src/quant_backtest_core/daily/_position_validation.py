from __future__ import annotations

from typing import cast

import pandas as pd

POSITIONS_BY_REBALANCE_REQUIRED_COLUMNS = ("rebalance_date", "symbol", "weight")


def _column_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return cast(pd.Series, frame[column])


def _parse_contract_dates(values: pd.Series) -> pd.Series:
    text = values.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    compact = text.str.fullmatch(r"\d{8}")
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    if bool(compact.any()):
        parsed.loc[compact] = pd.to_datetime(text.loc[compact], format="%Y%m%d", errors="coerce")
    remaining = ~compact
    if bool(remaining.any()):
        parsed.loc[remaining] = pd.to_datetime(text.loc[remaining], errors="coerce")
    return cast(pd.Series, parsed.dt.normalize())


def validate_positions_by_rebalance_frame(positions: pd.DataFrame) -> list[str]:
    """Return contract violations for a positions_by_rebalance artifact frame."""

    issues: list[str] = []
    missing = [
        column
        for column in POSITIONS_BY_REBALANCE_REQUIRED_COLUMNS
        if column not in positions.columns
    ]
    if missing:
        issues.append("missing columns: " + ", ".join(missing))
        return issues
    if positions.empty:
        return issues

    rebalance_dates = _parse_contract_dates(_column_series(positions, "rebalance_date"))
    if bool(rebalance_dates.isna().any()):
        issues.append("rebalance_date must be date-like")

    symbols = _column_series(positions, "symbol").astype("string")
    if bool(symbols.isna().any()) or bool(symbols.str.strip().eq("").any()):
        issues.append("symbol must be non-empty")

    weights = pd.to_numeric(_column_series(positions, "weight"), errors="coerce")
    if bool(weights.isna().any()):
        issues.append("weight must be numeric")
    return issues


def assert_positions_by_rebalance_frame(positions: pd.DataFrame) -> None:
    issues = validate_positions_by_rebalance_frame(positions)
    if issues:
        raise ValueError("Invalid positions_by_rebalance frame: " + "; ".join(issues))
