# Capability and compatibility matrix

**State: experimental, package 0.2.0, upstream NautilusTrader 0.66.0.**
Linux is the validated execution environment. Support below means synthetic cases
are exercised, not that all exchange rules or real-world data have been validated.

| Capability | Status | Entry point / boundary |
| --- | --- | --- |
| Independent library / CLI | Supported | No platform or runtime dependency |
| USD snapshot, quote market orders | Supported | `engine_request.v1` / runtime v5 |
| CNY/USD daily ledger | Supported | `engine_request.v2` / runtime v6 |
| Target-weight quantity planning | Supported, separate estimate | `size`; sale proceeds are projected, not guaranteed |
| Long-only cash account and uniform fee | Supported | Fee-inclusive cash admission; explicit fee bps |
| Configured T+1 and buy lots | Supported in v2 | Caller supplies sessions, flag and lot sizes |
| Halt / price-limit permissions | Explicit input only | Not inferred from exchange rules or prices |
| Quote-size partial fills / IOC remainder | Supported in v2 | Not a daily-volume participation model |
| No-lookahead order eligibility | Supported for declared clocks | Cannot prove upstream input was point-in-time correct |
| Dividends / splits / receivables / delisting policy | Unsupported | Retain Python backend; [conformance evidence](migration/corporate-action-conformance.md) |
| Exchange calendars, tax schedules, margin, shorts, FX | Unsupported | Do not infer from USD/CNY choice |
| Full platform execution-aware bundle | Not provided | Research clock, producer and provenance still required |
| Training / research validation / scheduling | Outside engine | Research layer / runtime own these |

## Tested provider and consumer revisions

The compatibility unit is a **source revision plus consumer revision**, not a
worktree directory or a mutable executable path. Both consumers build the provider
at `3ee74bfa21d743e595ce61d0ac06b97dd588ebd6` in dedicated real-binary CI.

| Consumer | Delivery | Integration |
| --- | --- | --- |
| quant-backtest-runtime | [v6 PR](https://github.com/runchengxie/quant-backtest-runtime/pull/39) | v5 snapshot retained; v6 session replay is opt-in |
| quant-platform | [adapter PR](https://github.com/runchengxie/quant-platform/pull/170) | Explicit `EngineClient`; Python default retained |

Runtime merge: `0c0e4315241240a09c84866287bbb24280adc4a3` (tested head `d38780e6d9f9a0209885d12ce932ed7efd701fce`).
Platform tested head: `e9e3eb14bddcfdedc4b1ce4a362f4a435652dd31`; use its PR merge and CI records for the delivery revision.
An executable SHA-256 identifies bytes; it does not identify a source revision by
itself. Deployments must retain both plus toolchain/build information.

## Upgrade policy

Keep wire schemas stable within their version; unsupported semantics fail rather
than silently degrade. Pin the provider, run [correctness cases](correctness.md)
and consumer integration tests before upgrading it. Experimental package versions
may change Rust APIs; there is no stable Rust API guarantee yet. Keep Python
fallbacks until the specific caller's required semantics and outputs are verified.

Platform merge: `db1ce93d0d311cf28fa087072ad1cedc70df05a1`。
