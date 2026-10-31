# Independent engine implementation plan

> **For agentic workers:** Use superpowers:executing-plans; implement sequentially.

**Goal:** Deliver a reusable Rust engine and CLI using upstream Nautilus execution.
**Architecture:** Strict request validation, one upstream adapter, normalized results;
no scheduler dependencies. Provider merges before consumers.
**Tech Stack:** Rust >=1.99.0, NautilusTrader =0.66.0, serde, decimal arithmetic.
**Spec:** docs/superpowers/specs/2026-10-31-independent-engine-design.md

## Global Constraints

Synthetic fixtures only; upstream =0.66.0; Rust >=1.99.0; decimal strings; UTC nanoseconds;
no self-written matching/accounting; no unsupported A-share capability claims.

## Review Focus

- Lookahead: intents must wait for a strictly later instrument quote.
- Precision/overflow: malformed decimals and timestamps return errors, never panics.
- Multi-asset valuation: every open position uses its own latest quote.
- Insufficient cash: report upstream rejection, never invent an executed fill.
- Repeated calls/processes: stable economic output without leaked global engine state.

### Task 1: Contract and validation

Files: Cargo.toml, src/contract.rs, src/lib.rs, tests/contract.rs, fixtures/*.json.
Interfaces: Request::validate() -> anyhow::Result<()>; strict serde Request and Result.
- [x] Write tests rejecting bad schema, unsupported capabilities, invalid decimals,
  unknown fields, duplicate IDs, invalid time order and information timing.
- [x] Run cargo test --test contract; observe missing behavior.
- [x] Implement contract validation and verify tests pass; commit.

### Task 2: Nautilus execution adapter

Files: src/nautilus.rs, src/strategy.rs, tests/engine.rs.
Interfaces: run(&Request) -> anyhow::Result<BacktestResult> exposed by src/lib.rs.
- [x] Add hand-derived roundtrip, fees, open position, multi-asset, rejection,
  no-lookahead and repeated-run tests; observe failure before implementation.
- [x] Translate quotes and intents into upstream instruments and Strategy callbacks;
  extract actual cached orders/fills/account balances/positions.
- [x] Run cargo test --locked; compare literal economic expectations; commit.

### Task 3: CLI, docs and CI

Files: src/main.rs, tests/cli.rs, README.md, README.zh-CN.md,
LICENSE*, docs/third-party-notices.md, .github/workflows/ci.yml.
Interfaces: quant-backtest-engine run REQUEST.json emits result JSON on stdout;
capabilities emits backend capability JSON; errors go to stderr and nonzero exit.
- [x] Test real CLI success, invalid input and stdout JSON purity before implementation.
- [x] Implement CLI; document schemas, market assumptions, usage and limitations.
- [x] Run fmt, clippy, locked tests, CLI fixture, diff check; independent review;
  fix important findings with regression tests; open/merge provider PR.

### Task 4: Opt-in consumers

Files: isolated runtime/platform worktrees; repository-specific tests and docs.
Interfaces: versioned subprocess request/result, explicit executable selection.
- [ ] Inspect consumer gates and design an additive request/result version if required.
- [ ] Test new path and legacy compatibility before implementing.
- [ ] Run all consumer-required checks against the merged provider revision.
- [ ] PR/merge in dependency order; record revisions and clean task resources.


## Delivery evidence

Engine PR #1 merged as `a2dc923b01c46389f090db7865175c5d87b6819c`:
16 real-upstream/contract/CLI tests passed; fmt, clippy, synthetic CLI and remote CI passed.
Runtime PR #37 merged as `e4ad3169d1897b93d04c3cb9e8f01c8e32b4a683`:
67 tests passed locally with the real engine, 80% combined coverage; remote docs,
Python 3.12/3.13 and pinned real-Rust integration checks passed. The v5 job contract
is additive and uses its own final-snapshot result schema, preserving v1-v4.
Platform boundary documentation is delivered separately; it changes no Python APIs.

Rulings: order quantities remain the first engine input, with weight sizing owned by
callers; the integrated release is LGPL-3.0-only; buy admission reserves upstream-rounded
fees and does not reuse same-callback sell proceeds. No market-rule parity or untrusted
code sandbox is claimed. These choices are documented in the public README.
