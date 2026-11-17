# SPDX-License-Identifier: Apache-2.0
"""Bounded finite forecast-path benchmark using MinuteSession as sole owner."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from itertools import product
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from quant_backtest_core.backtest._minute_checkpoint import _binding, _unwire
from quant_backtest_core.backtest.impact import LinearImpact
from quant_backtest_core.backtest.minute import MinuteExecutionConfig, MinuteExecutionResult
from quant_backtest_core.backtest.minute_session import MinuteSession


@dataclass(frozen=True)
class JointExecutionRequest:
    names: tuple[str, ...]
    decision_ns: int
    forecast_available_ns: int
    risk_available_ns: int
    forecast_bars: pd.DataFrame
    decision_times: tuple[int, ...]
    entry_times: tuple[int, ...]
    weight_choices: tuple[tuple[tuple[float, ...], ...], ...]
    config: MinuteExecutionConfig
    terminal_covariance: np.ndarray
    risk_aversion: float = 0.0
    past_bars: pd.DataFrame | None = None
    committed_targets: pd.DataFrame | None = None
    transient: float = 0.0
    permanent: float = 0.0
    decay_seconds: float = 1.0
    report_delay_seconds: float = 0.0
    max_evaluations: int = 4096


@dataclass(frozen=True)
class JointPathEvaluation:
    indices: tuple[int, ...]
    objective: float
    initial_nav: float
    terminal_nav: float
    risk_penalty: float
    result: MinuteExecutionResult
    decision_checkpoint: dict
    terminal_checkpoint: dict
    request_digest: str

    @property
    def evidence(self) -> dict[str, Any]:
        """Separate owner economic state from its causal delivered observation."""
        delivered, queue, trace = _unwire(self.terminal_checkpoint["delivery"])
        return {
            "decision_checkpoint": self.decision_checkpoint,
            "terminal_checkpoint": self.terminal_checkpoint,
            "owner_binding": self.terminal_checkpoint["binding"],
            "terminal_delivered": delivered,
            "terminal_report_queue": queue,
            "policy_trace": trace,
            "terminal_impact": self.terminal_checkpoint["impact"],
            "initial_nav_basis": "owner_economic_before_decision_event",
        }


@dataclass(frozen=True)
class JointExecutionPlan:
    indices: tuple[int, ...]
    first_weights: tuple[float, ...]
    evaluation: JointPathEvaluation
    status: str
    evaluation_count: int
    total_paths: int
    request_digest: str
    semantics: str = "forecast_contingent_terminal_marked_wealth_replan_after_first_action"


class _Policy:
    def __call__(self, state: Any, proposed: Any) -> Any:
        return None if state.pending_orders else proposed

    def checkpoint(self) -> dict[str, str]:
        return {"policy": "joint-execution-wait-pending.v1"}


def _snapshot(request: JointExecutionRequest) -> JointExecutionRequest:
    r = replace(
        request,
        names=tuple(request.names),
        decision_times=tuple(request.decision_times),
        entry_times=tuple(request.entry_times),
        weight_choices=tuple(tuple(tuple(w) for w in c) for c in request.weight_choices),
        forecast_bars=request.forecast_bars.copy(deep=True),
        past_bars=None if request.past_bars is None else request.past_bars.copy(deep=True),
        committed_targets=None
        if request.committed_targets is None
        else request.committed_targets.copy(deep=True),
        terminal_covariance=np.array(request.terminal_covariance, dtype=float, copy=True),
    )
    if (
        any(
            type(t) is not int
            for t in (r.decision_ns, r.forecast_available_ns, r.risk_available_ns)
        )
        or max(r.forecast_available_ns, r.risk_available_ns) > r.decision_ns
    ):
        raise ValueError("integer UTC clocks and as-of available forecasts/risk required")
    if type(r.config) is not MinuteExecutionConfig:
        raise ValueError("exact MinuteExecutionConfig required")
    if not math.isfinite(r.report_delay_seconds) or r.report_delay_seconds < 0:
        raise ValueError("finite nonnegative report delay required")
    n, h = len(r.names), len(r.decision_times)
    if (
        not n
        or len(set(r.names)) != n
        or any(not isinstance(s, str) or not s.strip() for s in r.names)
    ):
        raise ValueError("unique nonempty names required")
    if not 1 <= h <= 8 or len(r.entry_times) != h or len(r.weight_choices) != h:
        raise ValueError("horizon must be between 1 and 8 with aligned entries/choices")
    if type(r.max_evaluations) is not int or not 1 <= r.max_evaluations <= 100000:
        raise ValueError("evaluation budget must be between 1 and 100000")
    if r.decision_times[0] != r.decision_ns:
        raise ValueError("first decision must equal as-of clock")
    for i, (d, e, choices) in enumerate(
        zip(r.decision_times, r.entry_times, r.weight_choices, strict=True)
    ):
        if type(d) is not int or type(e) is not int or e <= d or (i and d <= r.entry_times[i - 1]):
            raise ValueError("strictly ordered decision/entry clocks required")
        if not 1 <= len(choices) <= 32:
            raise ValueError("each decision requires 1 to 32 choices")
        for w in choices:
            a = np.asarray(w, dtype=float)
            if a.shape != (n,) or not np.isfinite(a).all() or (a < 0).any() or a.sum() > 1 + 1e-12:
                raise ValueError("finite long-only weights summing to at most one required")
    cov = r.terminal_covariance
    if (
        cov.shape != (n, n)
        or not np.isfinite(cov).all()
        or not np.allclose(cov, cov.T, atol=1e-12, rtol=0)
        or np.linalg.eigvalsh(cov).min() < -1e-12
    ):
        raise ValueError("finite symmetric PSD terminal covariance required")
    if (
        not math.isfinite(r.risk_aversion)
        or r.risk_aversion < 0
        or not math.isfinite(r.config.initial_cash)
        or r.config.initial_cash <= 0
    ):
        raise ValueError("nonnegative risk and positive initial cash required")
    LinearImpact(transient=r.transient, permanent=r.permanent, decay_seconds=r.decay_seconds)
    for frame, past in ((r.past_bars, True), (r.forecast_bars, False)):
        if frame is None:
            continue
        required = {
            "time",
            "interval_start",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
        }
        if not required.issubset(frame.columns) or (not past and frame.empty):
            raise ValueError("complete nonempty forecast bars required")
        times = pd.DatetimeIndex(frame.time).as_unit("ns")
        starts = pd.DatetimeIndex(frame.interval_start).as_unit("ns")
        if times.tz is None or starts.tz is None or (starts.asi8 >= times.asi8).any():
            raise ValueError("timezone-aware bar clocks required")
        if (past and (times.asi8 > r.decision_ns).any()) or (
            not past and (times.asi8 <= r.decision_ns).any()
        ):
            raise ValueError("past/forecast bars must respect as-of boundary")
        if not set(frame.symbol).issubset(r.names) or frame.duplicated(["time", "symbol"]).any():
            raise ValueError("unique bars in fixed name universe required")
        numeric = frame[["open", "high", "low", "close", "volume", "amount"]].to_numpy(dtype=float)
        if (
            not np.isfinite(numeric).all()
            or (numeric[:, :4] <= 0).any()
            or (numeric[:, 4:] < 0).any()
        ):
            raise ValueError("finite positive forecast prices and nonnegative capacity required")
        if (
            (frame.low > frame.high)
            | (frame.low > frame.open)
            | (frame.low > frame.close)
            | (frame.high < frame.open)
            | (frame.high < frame.close)
        ).any():
            raise ValueError("consistent forecast OHLC required")
    if int(pd.DatetimeIndex(r.forecast_bars.time).as_unit("ns").asi8.max()) <= r.entry_times[-1]:
        raise ValueError("forecast must extend beyond final entry")
    if r.committed_targets is not None and not r.committed_targets.empty:
        prefix = r.committed_targets
        if not {"decision_time", "entry_time", "symbol", "weight"}.issubset(prefix.columns):
            raise ValueError("complete committed prefix targets required")
        weights = prefix.weight.to_numpy(dtype=float)
        if not np.isfinite(weights).all() or (weights < 0).any() or (weights > 1).any():
            raise ValueError("finite long-only committed prefix weights required")
        if (
            prefix.duplicated(["decision_time", "symbol"]).any()
            or (prefix.groupby("decision_time").weight.sum() > 1 + 1e-12).any()
        ):
            raise ValueError("unique prefix symbols with weight sum at most one required")
        if (
            pd.DatetimeIndex(prefix.entry_time).as_unit("ns").asi8
            <= pd.DatetimeIndex(prefix.decision_time).as_unit("ns").asi8
        ).any():
            raise ValueError("prefix entry must follow decision")
        for col in ("decision_time", "entry_time"):
            ts = pd.DatetimeIndex(r.committed_targets[col]).as_unit("ns")
            if ts.tz is None or (ts.asi8 > r.decision_ns).any():
                raise ValueError("committed prefix must be known at decision")
        if (
            pd.DatetimeIndex(r.committed_targets.decision_time).as_unit("ns").asi8 >= r.decision_ns
        ).any():
            raise ValueError("committed decisions must precede candidate decision")
        if (
            not set(r.committed_targets.symbol).issubset(r.names)
            or (r.committed_targets.weight < 0).any()
        ):
            raise ValueError("long-only committed prefix in name universe required")
    return r


def _evaluate(r: JointExecutionRequest, indices: tuple[int, ...]) -> JointPathEvaluation:
    if len(indices) != len(r.weight_choices) or any(
        type(i) is not int or not 0 <= i < len(c)
        for i, c in zip(indices, r.weight_choices, strict=True)
    ):
        raise ValueError("one valid choice index per decision required")
    rows = [
        dict(
            decision_time=pd.Timestamp(d, tz="UTC"),
            entry_time=pd.Timestamp(e, tz="UTC"),
            symbol=s,
            weight=w,
        )
        for d, e, c, i in zip(
            r.decision_times, r.entry_times, r.weight_choices, indices, strict=True
        )
        for s, w in zip(r.names, c[i], strict=True)
    ]
    targets = pd.DataFrame(rows)
    if r.committed_targets is not None:
        targets = pd.concat([r.committed_targets, targets], ignore_index=True)
    bars = pd.concat(
        [f for f in (r.past_bars, r.forecast_bars) if f is not None], ignore_index=True
    )
    session = MinuteSession(
        targets,
        bars,
        r.config,
        policy=_Policy(),
        report_delay_seconds=r.report_delay_seconds,
        impact=LinearImpact(
            transient=r.transient, permanent=r.permanent, decay_seconds=r.decay_seconds
        ),
    )
    while (
        session.cursor < len(session.simulation.times)
        and session.simulation.times[session.cursor].value < r.decision_ns
    ):
        session.step()
    decision_checkpoint = session.checkpoint()
    sim = session.simulation
    initial = float(sim.cash + sim.value())
    if not math.isfinite(initial) or initial <= 0:
        raise ValueError("positive known decision NAV required")
    while session.step():
        pass
    terminal_checkpoint = session.checkpoint()
    result = session.run()
    terminal = float(result.daily.iloc[-1].nav)
    exposures = np.array(
        [
            sim.holdings.get(s, 0) * sim.marks.get(s, float("nan")) if sim.holdings.get(s, 0) else 0
            for s in r.names
        ]
    )
    if not np.isfinite(exposures).all() or not math.isfinite(terminal):
        raise ValueError("known finite terminal marks required")
    risk = float(r.risk_aversion * 0.5 * exposures @ r.terminal_covariance @ exposures / initial)
    binding_targets = (
        pd.DataFrame(columns=["decision_time", "entry_time", "symbol", "weight"])
        if r.committed_targets is None
        else r.committed_targets.copy()
    )
    binding = _binding(
        binding_targets,
        bars,
        r.config,
        _Policy(),
        (),
        {"corporate_actions": (), "valuation_events": (), "capital_flows": ()},
    )
    payload = {
        "owner_binding": binding,
        "names": r.names,
        "decision_times": r.decision_times,
        "entry_times": r.entry_times,
        "budget": r.max_evaluations,
        "decision_ns": r.decision_ns,
        "forecast_available_ns": r.forecast_available_ns,
        "risk_available_ns": r.risk_available_ns,
        "choices": r.weight_choices,
        "covariance": r.terminal_covariance.tolist(),
        "gamma": r.risk_aversion,
        "impact": [r.transient, r.permanent, r.decay_seconds],
        "delay": r.report_delay_seconds,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return JointPathEvaluation(
        tuple(indices),
        initial - terminal + risk,
        initial,
        terminal,
        risk,
        result,
        decision_checkpoint,
        terminal_checkpoint,
        digest,
    )


def evaluate_joint_path(
    request: JointExecutionRequest, indices: tuple[int, ...]
) -> JointPathEvaluation:
    """Replay one forecast path; errors propagate and actual partial fills are retained."""
    return _evaluate(_snapshot(request), tuple(indices))


def solve_joint_execution(request: JointExecutionRequest) -> JointExecutionPlan:
    """Enumerate small grids; otherwise deterministic budgeted coordinate search.

    No lower bound or global certificate is supplied for incomplete search.
    """
    r = _snapshot(request)
    total = math.prod(map(len, r.weight_choices))
    seen: dict[tuple[int, ...], JointPathEvaluation] = {}

    def evaluate(path: tuple[int, ...]) -> JointPathEvaluation:
        if path not in seen:
            seen[path] = _evaluate(r, path)
        return seen[path]

    if total <= r.max_evaluations:
        for path in product(*(range(len(c)) for c in r.weight_choices)):
            evaluate(path)
        status = "optimal_exhaustive"
    else:
        current = tuple(0 for _ in r.weight_choices)
        evaluate(current)
        while len(seen) < r.max_evaluations:
            previous = current
            for t, c in enumerate(r.weight_choices):
                for i in range(len(c)):
                    path = current[:t] + (i,) + current[t + 1 :]
                    if path not in seen and len(seen) >= r.max_evaluations:
                        break
                    evaluate(path)
                current = min(seen, key=lambda p: (seen[p].objective, p))
            if current == previous:
                break
        status = "optimal_exhaustive" if len(seen) == total else "heuristic_budgeted"
    best = min(seen, key=lambda p: (seen[p].objective, p))
    value = seen[best]
    return JointExecutionPlan(
        best, r.weight_choices[0][best[0]], value, status, len(seen), total, value.request_digest
    )
