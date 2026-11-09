# Cost evidence

[简体中文](cost-evidence.zh-CN.md)

`quant_backtest_core.backtest.costs` provides the additive `cost_evidence.v1`
contract. It describes source costs without debiting cash, repricing fills or
estimating missing components. It imports no execution simulator.

```python
from quant_backtest_core.backtest.costs import CostComponents, CostEvidence

evidence = CostEvidence(
    source_id="synthetic-run:fill-0", source_revision="synthetic-owner-and-config-v1",
    stage="actual_fill_model", scope="fill", source_ids=("fill-0",),
    total=5, unallocated_total=2, components=CostComponents(commission=3),
    currency="CNY",
)
assert evidence.components.spread_cost is None
assert evidence.components_status == "partial"
assert evidence.to_mapping()["total"] == 5
```

Amounts are source account-currency units, never rates. `CostComponents` uses
`None` for unavailable evidence and zero only for a source-identified zero.
`CostEvidence` retains source/revision, stage, scope, accounting owner, currency,
unit, raw buckets and linked fill IDs. Source revision must identify both code
and configuration; IDs locate run-scoped evidence, not authenticated receipts.
`actual_fill_model` means simulated fills, not broker charges. Other stages are
`planned_estimate`, `aggregate_estimate` and `broker_actual`; the latter requires
independent broker sources, which this task does not acquire.

Validation requires finite amounts and
`total = sum(known components) + unallocated_total`. A signed residual preserves
source inconsistencies. Completeness is `unknown`, `partial` or
`source_identified`; bucket names do not identify causal economic effects.
`CostGroup` preserves the original minimum-fee scope, rule revision,
before/after notionals, optional order, market and schedule interval.
Both notionals must be present together and nondecreasing. A fill group does not
prove a broker-wide order/day rule.

Opportunity evidence requires a separate `economic_opportunity` accounting owner
and `opportunity_status="modeled"`; unknown/not-modeled opportunity components
remain `None`. Benchmark shortfall is descriptive and never an additional debit.
Impact already in fill price and cash fees are each counted once.

## Quotes and original charge owners

`CostQuote(currency, side, effective_ns, quantity, notional, commission, tax,
total, model_id, rounding)` is a frozen typed transport record. Money and
quantities are decimal strings; `effective_ns` is a string-safe UTC nanosecond
clock. `CostModel.quote(*, currency, side, effective_ns, quantity, price)`
is a protocol returning that record. Neither defines a fee formula, validates
a broker tariff, books cash or turns a preview into a fill. Concrete charge
adapters must delegate to the original charge owner and preserve its rounding,
grouping and source identity. No such owner is moved by this leaf task.

Legacy `CostBreakdown`, `ExecutionSimResult` and `ExecutionAdjustedNavResult`
adapters remain on Platform until their own transfer. Their evidence stays on
the original owner. Core does not import these classes or fabricate their output.
A known empty fill set is different from unsupported or missing evidence.

## Scoped fit evidence

`evidence.cost_scope.fit_cost_scope`, `validate_cost_scope` and
`validate_cost_scope_uncertainty` retain the original past-only fit, frozen
support checks and clustered bootstrap. Install `[cost]` for pandas, NumPy and
SciPy. See [transaction cost evidence](transaction-cost-evidence.md) for input
columns, completion/availability clocks, signed shortfall units, seed behavior,
cluster sufficiency and uncertainty limits. Later availability is not proof of
an unseen execution interval; no automatic promotion or future calibration
validity is claimed. Risk calibration and null-signal research remain in Platform.
[Source notices](../third-party-notices.md).
