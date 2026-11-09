"""Literal execution-only fixtures; no optimization or risk model lives here."""

from dataclasses import dataclass, replace
from types import SimpleNamespace

import pandas as pd


@dataclass(frozen=True)
class Request:
    current_weights: pd.Series
    lower_bounds: pd.Series
    upper_bounds: pd.Series
    expected_returns: pd.Series
    factor_loadings: pd.DataFrame
    factor_bounds: dict
    gross_limit: float
    net_target: float
    information_time: pd.Timestamp
    decision_time: pd.Timestamp


def factor_request(**changes):
    index = pd.Index(["a", "b", "c"])
    r = Request(
        pd.Series(0.0, index=index),
        pd.Series(-0.5, index=index),
        pd.Series(0.5, index=index),
        pd.Series([0.1, -0.1, 0], index=index),
        pd.DataFrame({"beta": [2.0, 1.0, 0.0]}, index=index),
        {},
        1.0,
        0.0,
        pd.Timestamp("2026-01-01", tz="UTC"),
        pd.Timestamp("2026-01-02", tz="UTC"),
    )
    return replace(r, **changes)


class LiteralOptimizer:
    def __init__(self, request, weights=(0.0, 0.0, 0.0), *, status="optimal"):
        self.request = request
        self.validated = False
        self.calls = []
        values = pd.Series(weights, index=request.current_weights.index)
        self.result = SimpleNamespace(
            status=status,
            message="literal test result",
            weights=values,
            turnover=float((values - request.current_weights).abs().sum()),
            caller_metadata=object(),
        )

    def validate(self, request):
        assert request is self.request
        self.validated = True

    def solve_pending(self, request, *, envelope, cash_limit):
        assert self.validated
        assert request is self.request
        self.calls.append((request, envelope, cash_limit))
        return self.result
