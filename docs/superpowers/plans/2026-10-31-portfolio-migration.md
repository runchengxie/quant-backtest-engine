# Portfolio migration implementation plan

> **For agentic workers:** Use superpowers:executing-plans for sequential implementation.

**Goal:** Deliver quantity planning and verified session-ledger/market-rule migration.
**Architecture:** A pure decimal sizing operation, upstream streaming engine batches,
and additive versioned runtime/platform adapters. Preserve v1/v5 behavior.
**Tech Stack:** Rust >=1.99.0, Nautilus =0.66.0, serde and Decimal, existing Python consumers.
**Spec:** docs/superpowers/specs/2026-10-31-portfolio-migration-design.md

## Global constraints

Synthetic inputs only; no second matcher/accountant; UTC nanoseconds; decimal strings;
no untested universal A-share claims; provider merges before consumers.

## Review focus

- Sizing uses only explicitly as-of marks, and never assumes a future fill price.
- Projected sale proceeds are estimates; execution always rechecks upstream free cash.
- Session snapshots are complete, fresh and reconciled from upstream state.
- T+1 eligibility and reservations are driven by actual fills/cancellations.
- Corporate-action primitives are not enough without cache/basis/portfolio propagation.

### Task 1: Pure target sizing

Files: src/sizing.rs, tests/sizing.rs, src/lib.rs, src/main.rs, fixtures/sizing.json.
Interfaces: size_targets(&SizingRequest) -> Result<SizingResult>; CLI `size FILE`.
Request includes schema, currency USD/CNY, cash, fee_bps, information_ts_ns and assets
with symbol, held_quantity, reference_price, price_ts_ns, target_weight and buy_lot.
All weights must be explicit, unique, long-only and sum <=1. Every price time <= information time.
Desired quantities floor weight*marked-equity/price to buy lots, retaining held odd lots
only for complete liquidation. Emit deterministic sells then buys, fee-aware affordable
quantities and projected cash; return desired vs planned quantities to expose residuals.
Projected sell proceeds may fund planned buys, explicitly requiring execution after sell
settlement; they are not authoritative account balances.
- [x] Add literal tests: 1000 cash, 50% at price10 ->50 shares; 100% with10bps ->99 shares,
  projected cash9.01; sell100 A/buy99 B ->projected cash8.01. Reject future marks,
  duplicate assets, weights>1, fractional quantities, bad lots and unknown fields.
- [x] Observe failing tests with a missing sizing implementation.
- [x] Implement and run full locked tests; commit.

### Task 2: Session ledger and rule contract

Files: src/sessions.rs, src/session_contract.rs, tests/sessions.rs and upstream helpers.
Interfaces: run_sessions(&SessionRequest) -> Result<SessionResult>; CLI run dispatch by schema.
- [x] Write hand-calculated two-session/no-trade/multi-asset/T+1/limits/lot tests.
- [x] Implement streaming batches and cache-derived snapshots with fresh explicit marks.
- [x] Enforce configured eligibility using upstream denial events and fill-driven reservations.
- [x] Test complete timestamps, missing marks and finalization; run full checks; commit.

### Task 3: Capacity/corporate-action conformance

Files: tests/conformance and docs/migration evidence.
- [x] Verify shared bid/ask consumption and IOC remainder against actual upstream.
- [x] Reproduce public cash/position adjustment propagation and basis/receivable semantics.
- [x] Implement only proven public-API extensions; record unsupported scenarios concretely.

### Task 4: Consumers and delivery

Files: runtime/platform isolated worktrees, new protocol/adapter tests and docs.
- [x] Add strict v2 result verification and opt-in runtime job version without changing old hashes.
- [x] Add platform sizing/result bridge and synthetic matched-reference tests.
- [x] Full required checks and independent review; provider then consumer PRs/merges.
- [x] Archive tested revision pairs and semantic limits; clean only task resources.

Delivery: provider PR #4; runtime PR #39; platform PR #170. Unsupported corporate actions remain a documented migration boundary rather than an implemented capability.
