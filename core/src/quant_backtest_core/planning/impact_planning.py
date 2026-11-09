# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/portfolio/impact_planning.py
# Original SHA256: f7aaf8cd7b778fcd394ef08fb66e34245c78976543d7b9493f1c303eaa7e6359
"""Convex QP with conservative affine cash bounds, continuous raw shares.

Economic cash is quadratic and is checked separately, never imposed as an
allegedly affine QP constraint. Only the first action is a candidate for owner
execution after quantity/fee/clock checks; subsequent actions are contingent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize

from quant_backtest_core.backtest.impact import LinearImpact


@dataclass(frozen=True)
class ImpactPlanningRequest:
    """CNY prices/cash, raw shares, return covariances, elapsed-second decay.

    Cash uses a capacity-derived conservative affine envelope. Fees and spread
    are fixed CNY/share; notional rates, minimum charges, lots and permanent
    impact are rejected. Initial transient displacement is as of decision_ns.
    All arrays use one caller-maintained name order. step_seconds has H-1 gaps;
    the first fill is at the decision clock. Locked holdings are horizon floors.
    """

    initial_holdings: np.ndarray
    initial_cash: float
    unaffected_prices: np.ndarray
    expected_returns: np.ndarray
    covariances: np.ndarray
    step_seconds: np.ndarray
    initial_transient: np.ndarray
    transient: np.ndarray
    decay_seconds: np.ndarray
    capacity: np.ndarray
    decision_ns: int
    forecast_available_ns: int
    risk_available_ns: int
    state_available_ns: int
    reserved_cash: float = 0.0
    locked_holdings: np.ndarray | None = None
    risk_aversion: float = 1.0
    fee_per_share: float | np.ndarray = 0.0
    spread_per_share: float | np.ndarray = 0.0
    units: str = "raw_shares_CNY"
    fee_rate: float = 0.0
    minimum_fee: float = 0.0
    quantity_step: float = 0.0
    permanent: float = 0.0


@dataclass(frozen=True)
class ImpactPlan:
    trades: tuple[tuple[float, ...], ...]
    first_action: tuple[float, ...]
    holdings: tuple[tuple[float, ...], ...]
    transient_before: tuple[tuple[float, ...], ...]
    transient_after: tuple[tuple[float, ...], ...]
    execution_prices: tuple[tuple[float, ...], ...]
    cash: tuple[float, ...]
    cash_lower_bounds: tuple[float, ...]
    objective: float
    maximum_violation: float
    residuals: dict[str, float]
    solver_success: bool
    solver_status: int
    solver_message: str
    request_digest: str
    formulation: str = "convex_qp_conservative_affine_cash.v1"
    impact_schema: str = "linear-impact.v1"
    semantics: str = "continuous_first_action_requires_owner_recheck_then_replan"


def _array(value, shape, name, *, nonnegative=False):
    array = np.array(value, dtype=float, copy=True)
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(f"{name}: finite array of shape {shape} required")
    if nonnegative and (array < 0).any():
        raise ValueError(f"{name}: nonnegative values required")
    return array


def _parameters(request):
    clocks = (
        request.decision_ns,
        request.forecast_available_ns,
        request.risk_available_ns,
        request.state_available_ns,
    )
    if any(type(value) is not int for value in clocks) or any(
        value > request.decision_ns for value in clocks[1:]
    ):
        raise ValueError("integer UTC nanosecond clocks and available inputs required")
    if request.units != "raw_shares_CNY" or any(
        value != 0
        for value in (
            request.fee_rate,
            request.minimum_fee,
            request.quantity_step,
            request.permanent,
        )
    ):
        raise ValueError("unsupported units, fee, quantity or permanent-impact semantics")
    scalars = (request.initial_cash, request.reserved_cash, request.risk_aversion)
    if any(not np.isfinite(v) or v < 0 for v in scalars):
        raise ValueError("finite nonnegative cash/reservation/risk parameters required")
    if request.reserved_cash > request.initial_cash:
        raise ValueError("reservations exceed initial cash")


def _inputs(request):
    _parameters(request)
    alpha = np.array(request.expected_returns, dtype=float, copy=True)
    if alpha.ndim != 2 or not all(alpha.shape) or not np.isfinite(alpha).all():
        raise ValueError("finite nonempty horizon/name returns required")
    periods, names = alpha.shape
    holdings = _array(request.initial_holdings, (names,), "holdings", nonnegative=True)
    prices = _array(request.unaffected_prices, (names,), "prices", nonnegative=True)
    if (prices == 0).any():
        raise ValueError("positive prices required")
    capacity = _array(request.capacity, alpha.shape, "capacity", nonnegative=True)
    initial = _array(request.initial_transient, (names,), "initial transient")
    impact = _array(request.transient, (names,), "transient", nonnegative=True)
    decay = _array(request.decay_seconds, (names,), "decay", nonnegative=True)
    if (decay == 0).any():
        raise ValueError("positive decay seconds required")
    gaps = _array(request.step_seconds, (periods - 1,), "step seconds", nonnegative=True)
    times = np.concatenate(([0.0], np.cumsum(gaps)))
    locked = _array(
        np.zeros(names) if request.locked_holdings is None else request.locked_holdings,
        (names,),
        "locked holdings",
        nonnegative=True,
    )
    if (locked > holdings).any():
        raise ValueError("locked holdings exceed initial holdings")
    fees = _array(
        np.broadcast_to(request.fee_per_share, (names,)),
        (names,),
        "fee per share",
        nonnegative=True,
    )
    spread = _array(
        np.broadcast_to(request.spread_per_share, (names,)),
        (names,),
        "spread per share",
        nonnegative=True,
    )
    covariance = _array(request.covariances, (periods, names, names), "covariances")
    for index, matrix in enumerate(covariance):
        if not np.allclose(matrix, matrix.T, atol=1e-12, rtol=0):
            raise ValueError("covariance must be symmetric PSD")
        eigenvalues, eigenvectors = np.linalg.eigh((matrix + matrix.T) / 2)
        if eigenvalues.min() < -1e-12:
            raise ValueError("covariance must be symmetric PSD")
        covariance[index] = (eigenvectors * np.maximum(eigenvalues, 0)) @ eigenvectors.T
    return (
        alpha,
        covariance,
        holdings,
        prices,
        capacity,
        initial,
        impact,
        decay,
        times,
        locked,
        fees,
        spread,
    )


def _quadratic(request, inputs):
    alpha, cov, holdings, prices, cap, initial, impact, decay, times, locked, fees, spread = inputs
    periods, names = alpha.shape
    size = alpha.size
    nav = float(request.initial_cash + holdings @ prices)
    if not np.isfinite(nav) or nav <= 0:
        raise ValueError("positive finite decision NAV required")
    cumulative = np.kron(np.tril(np.ones((periods, periods))), np.eye(names))
    previous = np.tile(holdings * prices / nav, periods)
    risk = np.zeros((size, size))
    kernel = np.zeros((size, size))
    envelope = np.empty_like(alpha)
    carry = np.exp(-times[:, None] / decay) * initial
    for t in range(periods):
        sl = slice(t * names, (t + 1) * names)
        risk[sl, sl] = request.risk_aversion * cov[t]
        envelope[t] = np.abs(carry[t]) + 0.5 * impact * cap[t]
        for s in range(periods):
            kernel[sl, s * names : (s + 1) * names] = np.diag(
                impact * np.exp(-abs(times[t] - times[s]) / decay) * nav / prices**2
            )
            if s < t:
                envelope[t] += impact * cap[s] * np.exp(-(times[t] - times[s]) / decay)
    if (envelope + spread >= prices).any():
        raise ValueError("capacity/state envelope must preserve positive execution prices")
    quadratic = cumulative.T @ risk @ cumulative + kernel
    linear = cumulative.T @ (risk @ previous - alpha.ravel()) + (carry / prices).ravel()
    constant = 0.5 * previous @ risk @ previous - alpha.ravel() @ previous
    fee = np.tile((fees + spread) / prices, periods)
    if not all(np.isfinite(v).all() for v in (quadratic, linear, envelope)):
        raise ValueError("nonfinite scaled QP")
    if np.linalg.eigvalsh(quadratic).min() < -1e-10 * max(1, np.linalg.norm(quadratic)):
        raise ValueError("QP Hessian must be PSD")
    # x = signed traded notional / NAV; z >= |x|.
    identity = np.eye(size)
    cash_map = np.kron(np.tril(np.ones((periods, periods))), np.ones((1, names)))
    cash_envelope = (envelope + fees + spread) / prices
    matrix = np.vstack(
        (
            np.hstack((-identity, identity)),
            np.hstack((identity, identity)),
            np.hstack((cumulative, np.zeros((size, size)))),
            np.hstack((-cash_map, -cash_map * cash_envelope.ravel())),
        )
    )
    lower = np.concatenate(
        (
            np.zeros(2 * size),
            np.tile((locked - holdings) * prices / nav, periods),
            np.full(periods, (request.reserved_cash - request.initial_cash) / nav),
        )
    )
    limit = (cap * prices / nav).ravel()
    bounds = Bounds(np.concatenate((-limit, np.zeros(size))), np.concatenate((limit, limit)))
    return nav, quadratic, linear, constant, fee, matrix, lower, bounds, envelope


def _replay(request, inputs, trades, envelope, nav):
    alpha, cov, previous, prices, cap, initial, impact, decay, times, locked, fees, spread = inputs
    models = [
        LinearImpact.restore(
            {
                "schema": "linear-impact.v1",
                "transient": float(k),
                "permanent": 0.0,
                "decay_seconds": float(tau),
                "states": {"asset": {"time": 0.0, "transient": float(d), "permanent": 0.0}},
            }
        )
        for k, tau, d in zip(impact, decay, initial, strict=True)
    ]
    before, after, execution, holdings, cash, lower = [], [], [], [], [], []
    position = previous.copy()
    balance = floor = request.initial_cash
    costs = 0.0
    for t, quantities in enumerate(trades):
        before.append([model.offset("asset", times[t]) for model in models])
        offsets = np.array(
            [
                model.execute("asset", times[t], q)
                for model, q in zip(models, quantities, strict=True)
            ]
        )
        after.append([model.offset("asset", times[t]) for model in models])
        fill_prices = prices + offsets + spread * np.sign(quantities)
        execution.append(fill_prices)
        position = position + quantities
        holdings.append(position.copy())
        balance -= quantities @ fill_prices + np.abs(quantities) @ fees
        floor -= quantities @ prices + np.abs(quantities) @ (envelope[t] + fees + spread)
        cash.append(balance)
        lower.append(floor)
        costs += quantities @ offsets + np.abs(quantities) @ (fees + spread)
    h = np.array(holdings)
    dollar = h * prices
    objective = (
        costs
        - float((alpha * dollar).sum())
        + 0.5
        * request.risk_aversion
        / nav
        * sum(row @ sigma @ row for row, sigma in zip(dollar, cov, strict=True))
    )
    residuals = {
        "holdings": max(0.0, float(np.max((locked - h) * prices / nav))),
        "capacity": max(0.0, float(np.max((np.abs(trades) - cap) * prices / nav))),
        "cash": max(0.0, (request.reserved_cash - min(cash)) / nav),
        "affine_cash": max(0.0, (request.reserved_cash - min(lower)) / nav),
        "cash_envelope": max(0.0, float(np.max(np.array(lower) - cash)) / nav),
        "positive_price": max(0.0, -float(np.min(np.array(execution) / prices))),
    }
    return holdings, before, after, execution, cash, lower, float(objective), residuals


def _request_digest(request):
    payload: dict[str, object] = {
        "implementation": "impact-planning.v1",
        "impact": "linear-impact.v1",
    }
    for name, value in asdict(request).items():
        if name.endswith("_ns") or isinstance(value, str) or value is None:
            payload[name] = value
        else:
            array = np.asarray(value, dtype="<f8")
            payload[name] = {"shape": array.shape, "float64_le_hex": array.tobytes().hex()}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def plan_with_impact(request: ImpactPlanningRequest) -> ImpactPlan:
    """Solve the declared conservative QP and independently replay economic cash.

    Solver success is reported, not a certificate of global numerical optimality.
    Residuals are dimensionless (cash/notional divided by decision NAV). No
    orders, reservations or fills are created by this research planning API.
    """
    request = ImpactPlanningRequest(**asdict(request))  # snapshot mutable input arrays
    inputs = _inputs(request)
    nav, quadratic, linear, constant, fee, matrix, lower, bounds, envelope = _quadratic(
        request, inputs
    )
    size = inputs[0].size

    def objective(vector):
        x, z = vector[:size], vector[size:]
        return float(0.5 * x @ quadratic @ x + linear @ x + fee @ z + constant)

    def gradient(vector):
        return np.concatenate((quadratic @ vector[:size] + linear, fee))

    solution = minimize(
        objective,
        np.zeros(2 * size),
        jac=gradient,
        method="SLSQP",
        bounds=bounds,
        constraints=[LinearConstraint(matrix, lower, np.inf)],
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    if not solution.success or not np.isfinite(solution.x).all():
        raise ValueError(f"failed impact QP: {solution.message}")
    trades = solution.x[:size].reshape(inputs[0].shape) * nav / inputs[3]
    holdings, before, after, execution, cash, floor, value, residuals = _replay(
        request, inputs, trades, envelope, nav
    )
    residuals["qp_constraints"] = max(0.0, float(np.max(lower - matrix @ solution.x)))
    residuals["qp_bounds"] = max(
        0.0, float(np.max(bounds.lb - solution.x)), float(np.max(solution.x - bounds.ub))
    )
    violation = max(residuals.values())
    if not np.isfinite(value) or violation > 1e-7:
        raise ValueError(f"invalid impact QP solution: violation={violation}")

    def rows(array):
        return tuple(tuple(float(v) for v in row) for row in array)

    return ImpactPlan(
        rows(trades),
        tuple(float(v) for v in trades[0]),
        rows(holdings),
        rows(before),
        rows(after),
        rows(execution),
        tuple(cash),
        tuple(floor),
        value,
        violation,
        residuals,
        bool(solution.success),
        int(getattr(solution, "status", 0)),
        str(solution.message),
        _request_digest(request),
    )
