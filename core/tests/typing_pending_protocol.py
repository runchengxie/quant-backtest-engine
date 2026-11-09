"""Static acceptance: original frozen caller fields satisfy read-only protocols."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from quant_backtest_core.planning.pending_protocol import PendingRequest, PendingSolveResult


@dataclass(frozen=True)
class ImmutableRequest:
    current_weights: pd.Series
    lower_bounds: pd.Series
    upper_bounds: pd.Series
    expected_returns: pd.Series
    factor_loadings: pd.DataFrame
    factor_bounds: Mapping[str, tuple[float, float]]
    gross_limit: float
    net_target: float
    information_time: pd.Timestamp
    decision_time: pd.Timestamp


@dataclass(frozen=True)
class ImmutableResult:
    status: Literal["optimal", "infeasible", "numerical_failure"]
    message: str
    weights: pd.Series | None


def accepts_caller_dataclasses(
    request: ImmutableRequest, result: ImmutableResult
) -> tuple[PendingRequest, PendingSolveResult]:
    return request, result
