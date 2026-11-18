"""Structural seam; research policy and the original request remain caller-owned."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal, Protocol

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .pending_allocation import PendingAllocationEnvelope


class PendingRequest(Protocol):
    """Only execution-relevant observations, bounds and clocks are owned here."""

    @property
    def current_weights(self) -> pd.Series: ...
    @property
    def lower_bounds(self) -> pd.Series: ...
    @property
    def upper_bounds(self) -> pd.Series: ...
    @property
    def expected_returns(self) -> pd.Series: ...
    @property
    def factor_loadings(self) -> pd.DataFrame: ...
    @property
    def factor_bounds(self) -> Mapping[str, tuple[float, float]]: ...
    @property
    def gross_limit(self) -> float: ...
    @property
    def net_target(self) -> float: ...
    @property
    def information_time(self) -> pd.Timestamp: ...
    @property
    def decision_time(self) -> pd.Timestamp: ...


class PendingSolveResult(Protocol):
    """The original structural result is retained, including caller metadata."""

    @property
    def status(self) -> Literal["optimal", "infeasible", "numerical_failure"]: ...
    @property
    def message(self) -> str: ...
    @property
    def weights(self) -> pd.Series | None: ...


class PendingOptimizer(Protocol):
    def validate(self, request: PendingRequest) -> None:
        """Validate the supplied optimizer's full request, including research policy."""
        ...

    def solve_pending(
        self,
        request: PendingRequest,
        *,
        envelope: PendingAllocationEnvelope,
        cash_limit: tuple[float, np.ndarray],
    ) -> PendingSolveResult:
        """Solve using tightened bounds without mutating the caller's request."""
        ...
