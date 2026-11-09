# Extracted from quant-platform/packages/platform/src/quant_platform/analytics/cost_scope.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Past-only signed fill-shortfall calibration with explicit applicability.

Shortfall is signed basis points against the decision mid, including fees once.
Participation is filled shares / contemporaneous market shares over the same
execution interval. Unfilled opportunity cost is not a fill-cost observation.
Coefficients do not identify permanent impact or authorize automatic promotion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import nnls


@dataclass(frozen=True)
class ScopedCostModel:
    intercept_bps: float
    impact_bps: float
    cutoff_ns: int
    side: str
    liquidity_bucket: str
    execution_minutes: int
    min_participation: float
    max_participation: float
    observations: int
    source_binding: str
    evidence_kind: str
    cost_basis: str = "signed_decision_mid_fill_shortfall_including_fees"

    def predict(self, participation, *, side, liquidity_bucket, execution_minutes):
        if (side, liquidity_bucket, execution_minutes) != (
            self.side,
            self.liquidity_bucket,
            self.execution_minutes,
        ):
            raise ValueError("cost scope mismatch")
        if (
            not np.isfinite(participation)
            or not self.min_participation <= participation <= self.max_participation
        ):
            raise ValueError("participation outside cost scope")
        return float(self.intercept_bps + self.impact_bps * np.sqrt(participation))


def _frame(observations):
    required = {
        "available_ns",
        "completed_ns",
        "participation",
        "filled_notional",
        "shortfall_bps",
        "side",
        "liquidity_bucket",
        "execution_minutes",
    }
    if not required <= set(observations):
        raise ValueError("missing cost observation columns")
    if any(type(v) is not int for v in observations.available_ns):
        raise ValueError("observation completion clocks must be integer UTC nanoseconds")
    if "completed_ns" not in observations or any(
        type(v) is not int for v in observations.completed_ns
    ):
        raise ValueError("integer execution completion clocks required")
    if (observations.completed_ns > observations.available_ns).any():
        raise ValueError("execution completion follows observation availability")
    return observations.copy()


def _numeric(frame):
    numbers = frame[["participation", "filled_notional", "shortfall_bps", "execution_minutes"]]
    if not np.isfinite(numbers.to_numpy(dtype=float)).all():
        raise ValueError("finite cost observations required")
    if (frame.participation <= 0).any() or (frame.filled_notional <= 0).any():
        raise ValueError("positive filled participation/notional required")
    if (frame.execution_minutes <= 0).any() or not frame.execution_minutes.map(
        lambda v: float(v).is_integer()
    ).all():
        raise ValueError("positive integer execution minutes required")
    if (
        not frame.side.isin(["buy", "sell"]).all()
        or not frame.liquidity_bucket.map(lambda v: isinstance(v, str) and bool(v.strip())).all()
    ):
        raise ValueError("explicit cost scope required")


def fit_cost_scope(
    observations: pd.DataFrame,
    *,
    cutoff_ns: int,
    source_binding: str,
    evidence_kind: str,
    min_observations: int = 3,
) -> ScopedCostModel:
    if type(cutoff_ns) is not int or not source_binding.strip() or min_observations < 3:
        raise ValueError("cutoff, source and minimum sample >=3 required")
    if evidence_kind not in {"synthetic", "broker_fills"}:
        raise ValueError("cost evidence kind must be explicit")
    frame = _frame(observations)
    frame = frame.loc[frame.available_ns <= cutoff_ns]
    if len(frame) < min_observations:
        raise ValueError("insufficient completed calibration observations")
    _numeric(frame)
    groups = frame[["side", "liquidity_bucket", "execution_minutes"]].drop_duplicates()
    if len(groups) != 1:
        raise ValueError("fit each cost scope separately")
    if frame.participation.nunique() < 2:
        raise ValueError("insufficient participation variation")
    weights = np.sqrt(frame.filled_notional.to_numpy(dtype=float) / frame.filled_notional.sum())
    design = np.column_stack(
        (np.ones(len(frame)), np.sqrt(frame.participation.to_numpy(dtype=float)))
    )
    coefficients, _ = nnls(
        design * weights[:, None], frame.shortfall_bps.to_numpy(dtype=float) * weights
    )
    group = groups.iloc[0]
    return ScopedCostModel(
        float(coefficients[0]),
        float(coefficients[1]),
        cutoff_ns,
        group.side,
        group.liquidity_bucket,
        int(group.execution_minutes),
        float(frame.participation.min()),
        float(frame.participation.max()),
        len(frame),
        source_binding,
        evidence_kind,
    )


def validate_cost_scope(
    model: ScopedCostModel, observations: pd.DataFrame, *, source_binding: str
) -> dict:
    if source_binding != model.source_binding:
        raise ValueError("validation source binding mismatch")
    frame = _frame(observations)
    frame = frame.loc[frame.available_ns > model.cutoff_ns]
    _numeric(frame)
    errors, weights = [], []
    unsupported = 0
    for row in frame.itertuples():
        try:
            predicted = model.predict(
                row.participation,
                side=row.side,
                liquidity_bucket=row.liquidity_bucket,
                execution_minutes=row.execution_minutes,
            )
        except ValueError:
            unsupported += 1
            continue
        errors.append(row.shortfall_bps - predicted)
        weights.append(row.filled_notional)
    return {
        "schema": "scoped-cost-validation.v1",
        "source_binding": source_binding,
        "observations": len(errors),
        "unsupported": unsupported,
        "cutoff_ns": model.cutoff_ns,
        "status": "evaluated" if errors else "insufficient_supported_holdout",
        "bias_bps": float(np.average(errors, weights=weights)) if errors else None,
        "rmse_bps": float(np.sqrt(np.average(np.square(errors), weights=weights)))
        if errors
        else None,
        "evidence_kind": model.evidence_kind,
        "promoted": False,
    }


def validate_cost_scope_uncertainty(
    model: ScopedCostModel,
    observations: pd.DataFrame,
    *,
    source_binding: str,
    cluster_column: str,
    cluster_kind: str,
    min_clusters: int = 3,
    bootstrap_samples: int = 1000,
    seed: int = 0,
) -> dict:
    """Bootstrap later supported residuals from an already frozen model.

    The caller must justify independent date/order clusters. Labels never verify
    independence or broker provenance. Intervals condition on the fitted model,
    and do not describe coefficient uncertainty or future market probabilities.
    """
    if (
        cluster_kind not in {"date", "order"}
        or not isinstance(cluster_column, str)
        or not cluster_column.strip()
    ):
        raise ValueError("explicit date/order cluster column required")
    if (
        type(min_clusters) is not int
        or min_clusters < 3
        or type(bootstrap_samples) is not int
        or bootstrap_samples < 100
        or type(seed) is not int
        or seed < 0
    ):
        raise ValueError("minimum >=3 clusters, >=100 bootstrap draws and integer seed required")
    report = validate_cost_scope(model, observations, source_binding=source_binding) | {
        "schema": "scoped-cost-cluster-validation.v1",
        "cluster_column": cluster_column,
        "cluster_kind": cluster_kind,
        "cluster_provenance": "caller_asserted",
        "independent_clusters": 0,
        "minimum_clusters": min_clusters,
        "bootstrap_samples": bootstrap_samples,
        "seed": seed,
        "confidence": 0.95,
        "bias_interval_bps": None,
        "rmse_interval_bps": None,
        "real_calibration": "unavailable",
        "uncertainty_status": "unavailable_clusters",
    }
    frame = _frame(observations)
    frame = frame.loc[frame.available_ns > model.cutoff_ns]
    frame = _supported_cost_rows(model, frame)
    if cluster_column not in frame or frame[cluster_column].isna().any():
        return report
    if (
        not frame[cluster_column]
        .map(lambda value: isinstance(value, str) and bool(value.strip()))
        .all()
    ):
        return report
    residuals = np.array(
        [
            row.shortfall_bps
            - model.predict(
                row.participation,
                side=row.side,
                liquidity_bucket=row.liquidity_bucket,
                execution_minutes=row.execution_minutes,
            )
            for row in frame.itertuples()
        ],
        dtype=float,
    )
    clusters = []
    # Keep caller columns untouched. Group indices are row positions, so the
    # separate residual buffer also aligns with duplicate/unsorted frame labels.
    for positions in frame.groupby(cluster_column, sort=True).indices.values():
        weight = frame.iloc[positions].filled_notional.to_numpy(dtype=float)
        errors = residuals[positions]
        clusters.append(
            [float(weight.sum()), float(np.dot(weight, errors)), float(np.dot(weight, errors**2))]
        )
    count = len(clusters)
    report["independent_clusters"] = count
    report["uncertainty_status"] = "insufficient_clusters"
    if count < min_clusters:
        return report
    # Resample whole clusters, never iid fills. Retain notional weighting.
    rng = np.random.default_rng(seed)
    array = np.array(clusters)
    bias, rmse = [], []
    for _ in range(bootstrap_samples):
        total_weight, signed, squared = array[rng.integers(0, count, count)].sum(axis=0)
        bias.append(signed / total_weight)
        rmse.append(np.sqrt(squared / total_weight))
    report["bias_interval_bps"] = np.quantile(bias, [0.025, 0.975]).tolist()
    report["rmse_interval_bps"] = np.quantile(rmse, [0.025, 0.975]).tolist()
    report["uncertainty_status"] = "evaluated"
    return report


def _supported_cost_rows(model, frame):
    supported = []
    for row in frame.itertuples():
        try:
            model.predict(
                row.participation,
                side=row.side,
                liquidity_bucket=row.liquidity_bucket,
                execution_minutes=row.execution_minutes,
            )
        except ValueError:
            supported.append(False)
        else:
            supported.append(True)
    return frame.loc[supported].copy()
