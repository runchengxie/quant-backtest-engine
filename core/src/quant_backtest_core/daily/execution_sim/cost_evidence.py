"""Source-aware bridge from simulator fills to the neutral cost contract."""

from __future__ import annotations

import pandas as pd

from quant_backtest_core.backtest.costs import CostComponents, CostEvidence, CostGroup

_COMPONENT_COLUMNS = {
    "commission": "cost_commission",
    "stamp_tax": "cost_stamp_tax",
    "transfer_fee": "cost_transfer_fee",
    "spread_cost": "cost_spread",
    "temporary_impact": "cost_temporary_impact",
    "permanent_impact": "cost_permanent_impact",
    "financing_cost": "cost_financing",
}


def simulator_cost_evidence(
    fills: pd.DataFrame, *, source_id: str, source_revision: str, currency: str | None = None
) -> tuple[CostEvidence, ...]:
    rows = []
    for position, (_, fill) in enumerate(fills.iterrows()):
        components = CostComponents(
            **{
                key: float(fill[col])
                for key, col in _COMPONENT_COLUMNS.items()
                if col in fill and pd.notna(fill[col])
            }
        )
        raw = {
            str(k): float(v)
            for k, v in fill.items()
            if (str(k).startswith("cost_") or k == "transaction_cost") and pd.notna(v)
        }
        group = _fill_group(fill, source_revision)
        total = float(fill["transaction_cost"])
        rows.append(
            CostEvidence(
                source_id=f"{source_id}:fill:{position}",
                source_revision=source_revision,
                source_ids=(f"{source_id}:fills:{position}",),
                stage="actual_fill_model",
                scope="fill",
                accounting_owner="simulator_cost_total",
                total=total,
                unallocated_total=total
                - sum(v for v in components.__dict__.values() if v is not None),
                components=components,
                raw_buckets=raw,
                group=group,
                currency=currency,
                opportunity_status="not_modeled",
            )
        )
    return tuple(rows)


def _optional_text(value: str | None) -> str | None:
    return None if value is None or pd.isna(value) else str(value)


def _fill_group(fill: pd.Series, source_revision: str) -> CostGroup | None:
    before = fill.get("fee_group_notional_before")
    after = fill.get("fee_group_notional_after")
    has_before, has_after = pd.notna(before), pd.notna(after)
    has_group = pd.notna(fill.get("fee_group_id"))
    if has_before != has_after or (has_before and not has_group):
        raise ValueError("Cumulative fee group evidence requires a group ID and both notionals")
    if not has_group:
        return None
    return CostGroup(
        group_id=str(fill["fee_group_id"]),
        rule_revision=source_revision,
        scope="order_execution_day" if has_before else "fill",
        notional_before=float(before) if has_before else None,
        notional_after=float(after) if has_after else None,
        order_id=_optional_text(fill.get("fee_order_id")),
        market=_optional_text(fill.get("fee_market")),
        period_start=_optional_text(fill.get("fee_period_start")),
        period_end=_optional_text(fill.get("fee_period_end")),
    )
