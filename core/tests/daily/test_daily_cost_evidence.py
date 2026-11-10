"""Synthetic cost evidence preserves accounting without inventing decomposition."""

import json
from dataclasses import replace

import pytest

from quant_backtest_core.daily.types import CostBreakdown


def test_aggregate_producer_keeps_unknown_components_and_original_buckets():
    original = CostBreakdown(86, 100)
    evidence = original.to_cost_evidence(source_id="leg-1", source_revision="synthetic-v1")
    assert evidence.total == 186
    assert evidence.unallocated_total == 186
    assert evidence.components_status == "unknown"
    assert all(v is None for v in evidence.to_mapping()["components"].values())
    assert evidence.raw_buckets == {"fee_cost": 86, "slippage_cost": 100}
    assert evidence.stage == "aggregate_estimate"
    assert evidence.currency is None
    assert json.loads(json.dumps(evidence.to_mapping()))["total"] == 186


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


def test_simulator_adopts_fill_components_and_dated_groups_without_repricing():
    from test_dated_execution_fees import _ledger_model, _run_continuous

    result = _run_continuous(
        amounts={"2020-01-02": 300.0, "2020-01-03": 300.0}, model=_ledger_model()
    )
    before = result.fills.copy(deep=True)
    rows = result.to_cost_evidence(source_id="run-1", source_revision="synthetic-v1")
    assert len(rows) == len(result.fills) == 2
    assert sum(r.total for r in rows) == pytest.approx(result.fills.transaction_cost.sum())
    assert sum(r.components.commission for r in rows) == 10
    assert rows[0].group.group_id != rows[1].group.group_id
    assert rows[0].group.notional_after == 300
    assert rows[0].stage == "actual_fill_model"
    assert rows[0].scope == "fill"
    assert rows[0].components.opportunity_cost is None
    assert rows[0].opportunity_status == "not_modeled"
    assert rows[0].raw_buckets["cost_opportunity"] == 0
    assert rows[0].unallocated_total == pytest.approx(0)
    assert rows[0].components_status == "partial"
    assert rows[0].source_ids
    assert result.fills.equals(before)


def test_no_fills_produces_no_cost_claims():
    from test_dated_execution_fees import _ledger_model, _run_continuous

    result = _run_continuous(amounts={"2020-01-02": 0.0, "2020-01-03": 0.0}, model=_ledger_model())
    assert result.to_cost_evidence(source_id="empty", source_revision="v1") == ()


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


def test_adapter_preserves_partial_source_and_never_turns_null_into_zero():
    import pandas as pd

    from quant_backtest_core.daily.execution_sim.results import ExecutionSimResult

    result = ExecutionSimResult(
        summary={},
        orders=pd.DataFrame(),
        fills=pd.DataFrame(
            [{"transaction_cost": 10.0, "cost_commission": 3.0, "cost_spread": None}]
        ),
    )
    (row,) = result.to_cost_evidence(source_id="run", source_revision="v1")
    assert row.components.commission == 3
    assert row.components.spread_cost is None
    assert row.unallocated_total == 7
    assert row.group is None


def test_fill_evidence_rejects_empty_locator_and_group_keeps_schedule_provenance():
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
    from test_dated_execution_fees import _ledger_model, _run_continuous

    result = _run_continuous(
        amounts={"2020-01-02": 300.0, "2020-01-03": 300.0}, model=_ledger_model()
    )
    first, *_ = result.to_cost_evidence(source_id="run", source_revision="v1")
    assert first.group.market == result.fills.iloc[0].fee_market
    assert first.group.order_id == result.fills.iloc[0].fee_order_id
    assert first.group.period_start == result.fills.iloc[0].fee_period_start


@pytest.mark.parametrize(
    "group_id,before,after", [("g", 0.0, None), ("g", None, 10.0), (None, 0.0, 10.0)]
)
def test_adapter_rejects_incomplete_group_lineage(group_id, before, after):
    import pandas as pd

    from quant_backtest_core.daily.execution_sim.results import ExecutionSimResult

    result = ExecutionSimResult(
        summary={},
        orders=pd.DataFrame(),
        fills=pd.DataFrame(
            [
                {
                    "transaction_cost": 5.0,
                    "fee_group_id": group_id,
                    "fee_group_notional_before": before,
                    "fee_group_notional_after": after,
                }
            ]
        ),
    )
    with pytest.raises(ValueError, match="group"):
        result.to_cost_evidence(source_id="run", source_revision="v1")
