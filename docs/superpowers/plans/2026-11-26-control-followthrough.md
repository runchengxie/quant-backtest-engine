# Execution follow-through implementation plan

[简体中文](2026-11-26-control-followthrough.zh-CN.md)

**Goal:** Explain incomplete owner executions and compare price drift, costs and inventory exposure.
**Architecture:** Independent synthetic study using the existing financial owner, frozen v1 adapters and external evidence export. No owner or production default changes.
**Spec:** docs/superpowers/specs/2026-11-26-control-followthrough-design.md

- [ ] Test-first independent reserve policy and moving-price fixture, preserving the existing v1 implementation. Check checkpoint binding and future prefix invariance.
- [ ] Test-first raw-bar valuation audit and drift/impact/fee/residual decomposition; hand arithmetic and no-oversell cases.
- [ ] Register fixed protocol before running; export lossless inputs, owner tables, failure flags and recovery receipts to a new DATA_ROOT task path.
- [ ] Independently review results and code; run installed Core/SDK, ownership, Rust, static and strict paired docs checks.
- [ ] PR to user's main, verify exact base/head and required CI, merge and clean only this task.

Review focus: stale delivered holdings, hard report gate, reserve infeasibility, incomplete terminal inventory and missing marks. No unavailable result is a zero-cost winner.
