# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/portfolio/multiperiod.py
# Original SHA256: 1ea34f11c9dbab02ea6560f983918ae1f418c5f40025f7faaafe14527ff94845
"""Finite-horizon long-only research planning, normalized to decision-time NAV.

Forecasts/risk are supplied estimates, not future realized data. Expected returns
are objective terms, not spendable cash. No terminal liquidation is assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, minimize


@dataclass(frozen=True)
class MultiPeriodRequest:
    expected_returns: np.ndarray
    covariances: np.ndarray
    previous_weights: np.ndarray
    decision_ns: int
    forecast_available_ns: int
    risk_aversion: float = 1.0
    cost_linear: float = 0.0
    cost_quadratic: float = 0.0
    max_weight: float = 1.0
    budget: float = 0.97
    max_trade: float = 1.0
    reserved_cash: float = 0.0
    tradable: np.ndarray | None = None


@dataclass(frozen=True)
class MultiPeriodPlan:
    weights: tuple[tuple[float, ...], ...]
    first_trade: tuple[float, ...]
    estimated_costs: tuple[float, ...]
    objective: float
    maximum_violation: float
    semantics: str = "forecast_plan_execute_first_then_replan"


def _inputs(request):
    if type(request.decision_ns) is not int or type(request.forecast_available_ns) is not int:
        raise ValueError("integer UTC nanosecond clocks required")
    if request.forecast_available_ns > request.decision_ns:
        raise ValueError("future forecast inputs")
    alpha = np.array(request.expected_returns, dtype=float, copy=True)
    cov = np.array(request.covariances, dtype=float, copy=True)
    previous = np.array(request.previous_weights, dtype=float, copy=True)
    if alpha.ndim != 2 or not all(alpha.shape) or previous.shape != (alpha.shape[1],):
        raise ValueError("invalid forecast/previous-weight dimensions")
    periods, names = alpha.shape
    if cov.shape != (periods, names, names):
        raise ValueError("invalid risk dimensions")
    if not all(np.isfinite(x).all() for x in (alpha, cov, previous)) or (previous < 0).any():
        raise ValueError("finite long-only inputs required")
    for matrix in cov:
        if (
            not np.allclose(matrix, matrix.T, atol=1e-12, rtol=0)
            or np.linalg.eigvalsh(matrix).min() < -1e-12
        ):
            raise ValueError("covariance must be symmetric PSD")
    _parameters(request, previous)
    tradable = (
        np.ones_like(alpha, dtype=bool)
        if request.tradable is None
        else np.asarray(request.tradable)
    )
    if tradable.shape != alpha.shape or tradable.dtype != np.dtype(bool):
        raise ValueError("tradability must be a boolean horizon/name array")
    return alpha, cov, previous, tradable


def plan_trades(request: MultiPeriodRequest) -> MultiPeriodPlan:
    alpha, cov, previous, tradable = _inputs(request)
    periods, _names = alpha.shape
    size = alpha.size

    def unpack(vector):
        weights = vector[:size].reshape(alpha.shape)
        absolute = vector[size:].reshape(alpha.shape)
        trades = weights - np.vstack((previous, weights[:-1]))
        costs = request.cost_linear * absolute.sum(axis=1) + 0.5 * request.cost_quadratic * (
            trades**2
        ).sum(axis=1)
        return weights, absolute, trades, costs

    def objective(vector):
        weights, _, _, costs = unpack(vector)
        risk = sum(w @ matrix @ w for w, matrix in zip(weights, cov, strict=True))
        return float(0.5 * request.risk_aversion * risk - (alpha * weights).sum() + costs.sum())

    def inequalities(vector):
        weights, absolute, trades, costs = unpack(vector)
        return np.concatenate(
            (
                (absolute - trades).ravel(),
                (absolute + trades).ravel(),
                (request.max_trade - trades).ravel(),
                (request.max_trade + trades).ravel(),
                request.budget - weights.sum(axis=1),
                1 - request.reserved_cash - weights.sum(axis=1) - np.cumsum(costs),
            )
        )

    initial_w = np.repeat(previous[None], periods, axis=0)
    initial = np.concatenate((initial_w.ravel(), np.zeros(size)))
    constraints = [{"type": "ineq", "fun": inequalities}]
    if not tradable.all():
        constraints.append({"type": "eq", "fun": lambda vector: unpack(vector)[2][~tradable]})
    lower = np.zeros(size * 2)
    upper = np.concatenate((np.full(size, request.max_weight), np.full(size, np.inf)))
    solution = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=Bounds(lower, upper),
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    weights, _, trades, costs = unpack(solution.x)
    residuals = [
        max(0.0, -float(inequalities(solution.x).min())),
        max(0.0, float(-weights.min())),
        max(0.0, float(weights.max() - request.max_weight)),
    ]
    if not tradable.all():
        residuals.append(float(np.abs(trades[~tradable]).max()))
    violation = max(residuals)
    if not solution.success or not np.isfinite(solution.x).all() or violation > 1e-7:
        raise ValueError(
            f"infeasible or failed multi-period solve: {solution.message}; violation={violation}"
        )
    return MultiPeriodPlan(
        tuple(tuple(float(v) for v in row) for row in weights),
        tuple(float(v) for v in trades[0]),
        tuple(float(v) for v in costs),
        objective(solution.x),
        violation,
    )


def _parameters(request, previous):
    parameters = (
        request.risk_aversion,
        request.cost_linear,
        request.cost_quadratic,
        request.max_weight,
        request.budget,
        request.max_trade,
        request.reserved_cash,
    )
    if any(not np.isfinite(v) or v < 0 for v in parameters):
        raise ValueError("finite nonnegative parameters required")
    if (
        request.max_weight > 1
        or request.budget > 1
        or request.reserved_cash > 1
        or previous.sum() > 1 + 1e-10
    ):
        raise ValueError("unlevered NAV fractions required")
