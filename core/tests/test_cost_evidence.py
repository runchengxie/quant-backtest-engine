# Extracted from quant-platform/tests/test_cost_evidence.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.


from dataclasses import replace

import pytest


def test_contract_rejects_unbalanced_and_nonfinite_evidence():
    from quant_backtest_core.backtest.costs import CostComponents, CostEvidence

    row = CostEvidence(
        source_id="leg",
        source_revision="v1",
        stage="aggregate_estimate",
        scope="aggregate_leg",
        total=10,
        unallocated_total=10,
    )
    with pytest.raises(ValueError, match="reconcile"):
        replace(row, components=CostComponents(commission=2))
    with pytest.raises(ValueError, match="finite"):
        replace(row, total=float("nan"))
    with pytest.raises(ValueError, match="stage"):
        replace(row, stage="actual")
    with pytest.raises(ValueError, match="fill"):
        replace(row, stage="actual_fill_model")


def test_group_rejects_unpaired_or_reversed_notionals():
    from quant_backtest_core.backtest.costs import CostGroup

    with pytest.raises(ValueError, match="both"):
        CostGroup("group", "rule-v1", "order_execution_day", notional_before=0)
    with pytest.raises(ValueError, match="ordered"):
        CostGroup("group", "rule-v1", "order_execution_day", 100, 50)


def test_opportunity_amount_requires_separate_accounting_owner():
    from quant_backtest_core.backtest.costs import CostComponents, CostEvidence

    with pytest.raises(ValueError, match="economic_opportunity"):
        CostEvidence(
            source_id="counterfactual",
            source_revision="v1",
            stage="planned_estimate",
            scope="aggregate_leg",
            total=3,
            unallocated_total=0,
            components=CostComponents(opportunity_cost=3),
            opportunity_status="modeled",
        )


def test_fill_evidence_rejects_empty_locator():
    # Leaf assertion from original test_fill_evidence_rejects_empty_locator_and_group_keeps_schedule_provenance.
    from quant_backtest_core.backtest.costs import CostEvidence

    with pytest.raises(ValueError, match="source IDs"):
        CostEvidence(
            source_id="run",
            source_revision="v1",
            stage="actual_fill_model",
            scope="fill",
            total=0,
            unallocated_total=0,
            source_ids=("",),
        )


def test_known_zero_unknown_components_and_signed_residual_remain_distinct():
    from quant_backtest_core.backtest.costs import CostComponents, CostEvidence, CostGroup

    row = CostEvidence(
        source_id="synthetic:fill-0",
        source_revision="owner-and-config-v1",
        source_ids=("fill-0",),
        stage="actual_fill_model",
        scope="fill",
        total=5,
        unallocated_total=-2,
        components=CostComponents(commission=7, stamp_tax=0),
        raw_buckets={"original_fee": 5},
        currency="CNY",
        group=CostGroup("g", "rule-v1", "order_execution_day", 0, 100, "order-1", "SYNTH"),
    )
    payload = row.to_mapping()
    assert payload["total"] == 5
    assert payload["unallocated_total"] == -2
    assert payload["components"]["stamp_tax"] == 0
    assert payload["components"]["spread_cost"] is None
    assert payload["components_status"] == "partial"
    assert payload["opportunity_status"] == "unknown"
    assert payload["group"]["notional_after"] == 100
    assert payload["raw_buckets"] == {"original_fee": 5}
