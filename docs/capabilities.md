# Capability and compatibility matrix

Package 0.2.0 is experimental and uses NautilusTrader 0.66.0.
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
| Training / research validation | Outside engine | Research layer owns these |
| Job submission, state and process management | Outside engine | Provided by runtime; a persistent scheduler and global queue require separate implementation |

## Tested provider and consumer revisions

The compatibility unit is a source revision plus a consumer revision, not a
worktree directory or a mutable executable path. The table records merged integrations.

| Component | Merged revision / delivery | Tested provider and boundary |
| --- | --- | --- |
| Independent Python SDK | `f0ba2ef193c721c7bd497c4d80a7bc8a01c18a31`, [PR #7](https://github.com/runchengxie/quant-backtest-engine/pull/7) | Dependency-free installed wheel; raw JSON size/session results |
| quant-backtest-runtime | `bb1f20eeab1105b9001663ec6e39ab523b57d8ea`, [PR #41](https://github.com/runchengxie/quant-backtest-runtime/pull/41) | Real CLI provider `341de0177bc3e6b95ff8b4abb8c80c83eaedf207`; core install has no platform dependency, old jobs use `legacy` extra |
| quant-platform | `3ac555bbfc8dba69d1a910320d5eefe947122df3`, [PR #171](https://github.com/runchengxie/quant-platform/pull/171) | SDK and CLI pinned to `f0ba2ef193c721c7bd497c4d80a7bc8a01c18a31`; `engine` extra and canonical table mapping only |

The platform's historical source directory is retired. New public owners are
`quant_platform.portfolio`, `quant_platform.analytics` and `quant_platform.backtest`.
The old `portfolio_backtester` namespace remains compatibility aliases; retained
Python execution is explicit under `quant_platform.backtest.legacy`. See the
[ownership and removal gates](https://runchengxie.github.io/quant-platform/migration/portfolio-boundaries/).
Moving imports does not prove Rust parity for corporate actions, capacity or full
execution-aware evidence. No production task or dataset is switched by this migration.

Earlier v6/adapter baselines remain recorded in
[runtime PR #39](https://github.com/runchengxie/quant-backtest-runtime/pull/39) and
[platform PR #170](https://github.com/runchengxie/quant-platform/pull/170).
Executable SHA-256 checks byte identity. Retain source and build records alongside
the byte hash when deploying, and verify any publisher signature separately.

## Upgrade policy

Keep wire schemas stable within their version; unsupported semantics fail rather
than silently degrade. Pin the provider, run [correctness cases](correctness.md)
and consumer integration tests before upgrading it. Experimental package versions
may change Rust APIs; there is no stable Rust API guarantee yet. Keep Python
fallbacks until the specific caller's required semantics and outputs are verified.
