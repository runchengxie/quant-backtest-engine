"""Conservative financial evidence projection; no research statistics or new ledger."""

from math import isfinite

import pandas as pd

from .contracts import DailySummaryEvidence, ExecutionSummary

_FEE_COLUMNS = ("cost_commission", "cost_stamp_tax", "cost_transfer_fee")


def _finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def summarize_execution(
    daily: pd.DataFrame, fills: pd.DataFrame, *, evidence: DailySummaryEvidence | None = None
) -> ExecutionSummary:
    count = len(daily)
    if evidence is None:
        return ExecutionSummary((None,) * count, None, None, None, False)
    marks, flows = evidence.valuation_complete_by_row, evidence.external_flow_zero_by_row
    if len(marks) != count or len(flows) != count:
        raise ValueError("summary evidence must align exactly with daily row order")
    if evidence.daily_status == "unavailable" and not daily.empty:
        raise ValueError("unavailable daily evidence contradicts supplied rows")
    if evidence.fills_status == "unavailable" and not fills.empty:
        raise ValueError("unavailable fills evidence contradicts supplied rows")
    available = evidence.daily_status == "available"
    values = daily["executed_return"] if "executed_return" in daily else (None,) * count
    returns = tuple(
        _finite(value) if available and mark is True and flow is True else None
        for value, mark, flow in zip(values, marks, flows, strict=True)
    )
    cumulative = None
    if available and all(value is not None for value in returns):
        # Original product-minus-one arithmetic, over the FULL supported sequence.
        cumulative = _finite((1.0 + pd.Series(returns, dtype=float)).prod() - 1.0)
    total_fees = None
    if evidence.fills_status == "available" and all(col in fills for col in _FEE_COLUMNS):
        components = [_finite(value) for col in _FEE_COLUMNS for value in fills[col]]
        if all(value is not None for value in components):
            total_fees = _finite(sum(value for value in components if value is not None))
    return ExecutionSummary(
        returns,
        cumulative,
        None,
        total_fees,
        available and all(value is True for value in marks),
    )
