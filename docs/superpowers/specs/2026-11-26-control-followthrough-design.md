# Execution failure and price-risk follow-through

[简体中文](2026-11-26-control-followthrough-design.zh-CN.md)

Extend the frozen synthetic owner study without changing its fixtures, checkpoint semantics or the financial owner. The user authorized failure attribution, conservative feedback handling, terminal capacity reserve and moving-price comparisons.

## Approach

Reuse MinuteSession for every financial result. Add an independent follow-through experiment rather than altering the frozen v1 study. A new reserve controller plans against one fewer remaining slot while submitting on the existing clock; it has no future actual price, impact or volume access. Compare it with the four existing policies, including rolling without reserve. Deterministic price paths (flat, up, down, oscillating, late jump) are scenarios, not forecasts or market samples.

A reservation-only policy cannot bypass MinuteSession's hard undelivered-report gate. Diagnose this limitation explicitly; do not weaken the owner or pretend to have tested a concurrent-order protocol. Record available delivered holdings, pending quantities and the report gate, never infer hidden fills. Reserve infeasibility remains a failure, never a forced fill.

## Outputs and checks

Attribute incomplete outcomes using overlapping evidence flags: forecast planning infeasibility, waiting for pending reports/orders, insufficient realized capacity and missed fixed submission. Flags describe mechanisms, not identified causal shares. Compare fixed price paths with identical scenario identities and controls. Separate realized execution deviation from observed raw bar price, price drift relative to the initial benchmark, actual fees and terminal residual mark. Full-target marked shortfall includes residual inventory; completed-only execution rankings stay separate. Inventory exposure is measured from owner fill prefixes, is not a cash debit, and does not claim stochastic risk reduction.

Audit actual owner cash, fees, quantities and each daily mark against the corresponding last raw bar. Never use a flat benchmark to value moving-price holdings. Test future-path prefix invariance and every-boundary recovery for reserve, malformed/changed configuration rejection, no overselling and zero-impact arithmetic. Keep all generated data in a new external task directory. Fixed panels and source fingerprints precede results; preserve failed attempts.

Research separately reuses an existing frozen historical panel and documents all existing conditional/tail evidence, execution gaps and data trust. No 2026 holdout, production pointer or fabricated held-position marks. Engine contains synthetic inputs only. Provider merges precede any consumer changes.
