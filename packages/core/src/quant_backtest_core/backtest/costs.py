# Extracted from quant-platform/packages/platform/src/quant_platform/backtest/costs.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Neutral, additive cost evidence; amounts are source account units, never rates.

Component names identify implementation buckets, not measured economic effects.
Evidence records describe costs; they never instruct a consumer to debit cash.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from math import isclose, isfinite
from types import MappingProxyType
from typing import Any, Protocol

COST_EVIDENCE_SCHEMA = "cost_evidence.v1"


def _finite(value: float, label: str) -> None:
    if isinstance(value, bool) or not isfinite(value):
        raise ValueError(f"{label} must be finite numeric amounts")


@dataclass(frozen=True)
class CostComponents:
    """None is unavailable; zero is a source-identified implementation zero."""

    commission: float | None = None
    stamp_tax: float | None = None
    transfer_fee: float | None = None
    spread_cost: float | None = None
    temporary_impact: float | None = None
    permanent_impact: float | None = None
    opportunity_cost: float | None = None
    financing_cost: float | None = None

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if value is not None:
                _finite(value, key)


@dataclass(frozen=True)
class CostGroup:
    """Source minimum-fee group; no assertion of broker-wide rule equivalence."""

    group_id: str
    rule_revision: str
    scope: str
    notional_before: float | None = None
    notional_after: float | None = None
    order_id: str | None = None
    market: str | None = None
    period_start: str | None = None
    period_end: str | None = None

    def __post_init__(self) -> None:
        if not self.group_id.strip() or not self.rule_revision.strip():
            raise ValueError("Cost group requires an ID and rule revision")
        if self.scope not in {"order_execution_day", "fill", "broker_group"}:
            raise ValueError("Unsupported cost group scope")
        if (self.notional_before is None) != (self.notional_after is None):
            raise ValueError("Cumulative group notionals require both before and after")
        if self.notional_before is not None and self.notional_after is not None:
            _finite(self.notional_before, "notional_before")
            _finite(self.notional_after, "notional_after")
            if not 0 <= self.notional_before <= self.notional_after:
                raise ValueError("Cumulative group notionals must be nonnegative and ordered")


@dataclass(frozen=True)
class CostEvidence:
    """Reconciled source evidence, separate from historical accounting tables.

    Source revision must bind the implementation and configuration used by the
    producer. Source IDs are run-scoped evidence locators, not broker receipts.
    ``total`` retains the source booked/model amount; unallocated_total retains
    everything not identified by components. Noncash opportunity evidence uses
    a separate accounting owner and is never silently added to booked costs.
    """

    source_id: str
    source_revision: str
    stage: str
    scope: str
    total: float
    unallocated_total: float
    components: CostComponents = field(default_factory=CostComponents)
    source_ids: tuple[str, ...] = ()
    accounting_owner: str = "source_cost_total"
    currency: str | None = None
    unit: str = "account_currency_amount"
    opportunity_status: str = "unknown"
    raw_buckets: Mapping[str, float] = field(default_factory=dict)
    group: CostGroup | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.source_revision.strip():
            raise ValueError("Cost evidence requires source ID and revision")
        if self.stage not in {
            "planned_estimate",
            "aggregate_estimate",
            "actual_fill_model",
            "broker_actual",
        }:
            raise ValueError("Unsupported cost evidence stage")
        if self.scope not in {"aggregate_leg", "fill", "order_execution_day", "broker_group"}:
            raise ValueError("Unsupported cost evidence scope")
        if self.stage == "actual_fill_model" and (
            self.scope != "fill" or not self.source_ids or not all(self.source_ids)
        ):
            raise ValueError("Actual fill model evidence requires linked fill source IDs")
        if not self.accounting_owner.strip() or self.unit != "account_currency_amount":
            raise ValueError("Cost evidence requires accounting owner and amount unit")
        if self.currency is not None and not self.currency.strip():
            raise ValueError("Use None for unknown currency")
        self._validate_opportunity()
        _finite(self.total, "total")
        _finite(self.unallocated_total, "unallocated_total")
        known = sum(v for v in asdict(self.components).values() if v is not None)
        if not isclose(self.total, known + self.unallocated_total, rel_tol=1e-10, abs_tol=1e-8):
            raise ValueError("Cost components and unallocated_total must reconcile to total")
        raw = dict(self.raw_buckets)
        for key, value in raw.items():
            _finite(value, key)
        object.__setattr__(self, "raw_buckets", MappingProxyType(raw))
        object.__setattr__(self, "source_ids", tuple(self.source_ids))

    def _validate_opportunity(self) -> None:
        if (
            self.components.opportunity_cost is not None
            and self.accounting_owner != "economic_opportunity"
        ):
            raise ValueError("Opportunity components require economic_opportunity accounting owner")
        if self.opportunity_status not in {"unknown", "not_modeled", "modeled"}:
            raise ValueError("Unsupported opportunity status")
        if self.opportunity_status != "modeled" and self.components.opportunity_cost is not None:
            raise ValueError("Unknown/unmodeled opportunity cost must be None")

    @property
    def components_status(self) -> str:
        available = [v is not None for v in asdict(self.components).values()]
        if all(available):
            return "source_identified"
        return "partial" if any(available) else "unknown"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": COST_EVIDENCE_SCHEMA,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "source_ids": list(self.source_ids),
            "stage": self.stage,
            "scope": self.scope,
            "accounting_owner": self.accounting_owner,
            "currency": self.currency,
            "unit": self.unit,
            "total": self.total,
            "unallocated_total": self.unallocated_total,
            "components": asdict(self.components),
            "components_status": self.components_status,
            "opportunity_status": self.opportunity_status,
            "raw_buckets": dict(self.raw_buckets),
            "group": None if self.group is None else asdict(self.group),
        }


# Engine addition: typed transport only; original financial owners compute charges.
@dataclass(frozen=True)
class CostQuote:
    """Explicit source quote, not a fill or an instruction to debit cash.

    Money and quantity are decimal strings; effective_ns is an exact UTC
    nanosecond string. The source owner supplies model_id and rounding.
    This record performs no repricing, fee calculation or accounting mutation.
    """

    currency: str
    side: str
    effective_ns: str
    quantity: str
    notional: str
    commission: str
    tax: str
    total: str
    model_id: str
    rounding: str


class CostModel(Protocol):
    """A quote adapter delegates arithmetic to its original financial owner."""

    def quote(
        self, *, currency: str, side: str, effective_ns: str, quantity: str, price: str
    ) -> CostQuote: ...
