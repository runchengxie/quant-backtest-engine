# Correctness evidence and migration decisions

The primary baseline is a set of hand-computable synthetic economic cases run
against the real upstream engine. Passing them is necessary for upgrades; it is
not evidence that every market mechanism or production dataset is correct.

| Case | Expected behavior | Executable evidence |
| --- | --- | --- |
| Buy 10 at 10, sell at 12, fee 10 bps | Cash/NAV 10019.78; fee 0.22 | `tests/engine.rs::upstream_roundtrip_accounts_for_fees_and_no_lookahead` |
| Open holding marked at last quote | Cash 9899.9 + position 110 = NAV 10009.9 | `tests/engine.rs::upstream_marks_open_positions_and_is_repeatable` |
| Exact cash cannot cover commission | Denial, no fabricated fill | `tests/engine.rs::cash_admission_includes_upstream_rounded_commission` |
| 10% weight and configured T+1 | Day-one NAV 10099; same-day denial; final 10197.8 | [Executable walkthrough](tutorial.md) and `tests/sessions.rs` |
| Insufficient displayed liquidity | Actual partial fill; IOC remainder canceled | `tests/sessions.rs::quote_liquidity_is_shared_and_ioc_does_not_invent_capacity` |
| Missing/stale marks or adjusted prices | Explicit failure | `tests/sessions.rs::rejects_missing_or_stale_session_valuation_and_adjusted_prices` |
| Same inputs, repeated calls/processes | Identical normalized JSON | Engine tests and [batch digest checks](benchmarks.md) |
| Quantity adjustment used as stock split | Does not rebase cost correctly | [Corporate-action conformance](migration/corporate-action-conformance.md): retain Python |

Run `cargo test --locked` and the walkthrough before changing the pinned upstream.
Consumers additionally reconcile fills/cash/holdings and bind valuation marks to
the request's valuation quote midpoint. A balanced result with inflated marks must
fail; arithmetic consistency alone cannot establish price correctness.

## A narrow Python comparison

With the existing `quant-platform` installed in a separate Python environment:

```sh
/path/to/platform-python project_tools/compare_python.py \
  --engine /absolute/path/to/quant-backtest-engine \
  --output /absolute/external/path/new-comparison.json
```

The case fully invests CNY 10,000 at 10 and sells at 12 with zero fees. The current
Python `NativePositionReplayBackend` reports floating-point return
`0.19999999999999996`; the pinned Rust provider reports decimal return `0.2` and
NAV `12000`. The check uses absolute return tolerance `1e-12` for the Python float.
This experiment used provider `3ee74bfa21d743e595ce61d0ac06b97dd588ebd6`
and platform source `35055445ffcbd86c26cd4d3017b3fe0e14b4ee2a`
(the subsequently added adapter does not change that reference backend).

Only period return is compared. Python period-close replay and Rust explicit
quote/session execution differ in timing and input representation. This case
compares neither daily marks nor fee-inclusive sizing, partial fills, taxes,
corporate actions or complete ledger parity. Do not treat the Python output or
the Rust output as an oracle for mechanisms that have not been aligned and tested.

## Before migrating a caller

List its required data availability times, order/valuation conventions, currencies,
fees, settlement, corporate actions and expected outputs. Mark each against the
[capability matrix](capabilities.md). Run representative synthetic cases through
both paths and explain differences before switching. Keep the Python path when
an essential mechanism is unsupported. Portfolio performance is not a substitute
for reconciling cash, shares and fills.
