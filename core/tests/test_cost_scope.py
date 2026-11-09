# Extracted from quant-platform/tests/test_cost_scope.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
import pandas as pd
import pytest

from quant_backtest_core.evidence.cost_scope import fit_cost_scope, validate_cost_scope


def observations():
    return pd.DataFrame(
        [
            {
                "available_ns": i,
                "completed_ns": i,
                "participation": p,
                "filled_notional": 100.0,
                "shortfall_bps": 2 + 10 * p**0.5,
                "side": "buy",
                "liquidity_bucket": "liquid",
                "execution_minutes": 30,
            }
            for i, p in enumerate((0.01, 0.04, 0.09, 0.01, 0.04, 0.09), 1)
        ]
    )


def test_fit_uses_completed_past_only_and_declares_scope():
    frame = observations()
    model = fit_cost_scope(
        frame, cutoff_ns=3, source_binding="synthetic-v1", evidence_kind="synthetic"
    )
    assert model.intercept_bps == pytest.approx(2)
    assert model.impact_bps == pytest.approx(10)
    frame.loc[frame.available_ns > 3, "shortfall_bps"] = 10000
    changed = fit_cost_scope(
        frame, cutoff_ns=3, source_binding="synthetic-v1", evidence_kind="synthetic"
    )
    assert changed == model
    assert model.predict(
        0.04, side="buy", liquidity_bucket="liquid", execution_minutes=30
    ) == pytest.approx(4)
    with pytest.raises(ValueError, match="scope"):
        model.predict(0.9, side="buy", liquidity_bucket="liquid", execution_minutes=30)


def test_holdout_retains_signed_errors_and_unsupported_rows():
    frame = observations()
    model = fit_cost_scope(frame, cutoff_ns=3, source_binding="s", evidence_kind="synthetic")
    frame.loc[frame.available_ns > 3, "shortfall_bps"] -= 1
    report = validate_cost_scope(model, frame, source_binding=model.source_binding)
    assert report["bias_bps"] == pytest.approx(-1)
    assert report["observations"] == 3
    frame.loc[5, "side"] = "sell"
    assert (
        validate_cost_scope(model, frame, source_binding=model.source_binding)["unsupported"] == 1
    )


def test_incomplete_or_mixed_training_evidence_rejected():
    frame = observations()
    with pytest.raises(ValueError, match="insufficient"):
        fit_cost_scope(frame, cutoff_ns=1, source_binding="s", evidence_kind="synthetic")
    frame.loc[0, "side"] = "sell"
    with pytest.raises(ValueError, match="scope"):
        fit_cost_scope(frame, cutoff_ns=3, source_binding="s", evidence_kind="synthetic")


def test_validation_rejects_foreign_source_and_unfinished_observations():
    frame = observations()
    model = fit_cost_scope(frame, cutoff_ns=3, source_binding="owned", evidence_kind="synthetic")
    with pytest.raises(ValueError, match="source"):
        validate_cost_scope(model, frame, source_binding="foreign")
    frame["completed_ns"] = frame.available_ns + 1
    with pytest.raises(ValueError, match="completion"):
        fit_cost_scope(frame, cutoff_ns=3, source_binding="owned", evidence_kind="synthetic")
