# Remaining portfolio-engine migration

## Owner intent and execution

The owner asked to advance all remaining migration work in normal mode, delegating
implementation decisions. Preserve the independent Rust engine, thin upstream
execution, backwards-compatible old APIs and explicit capabilities. Production switching
requires parity evidence; do not silently redirect running/private research jobs.
The documentation site and notices layout are a separately deliverable concurrent task.

## Approach

Reuse Nautilus streaming replay and cached orders/accounts/positions, adding explicit
session boundaries, validated market constraints and per-session snapshots. Do not
write another matcher or cash account. Keep target sizing a pure, separately callable
portfolio operation. Prefer public upstream event/fee/module APIs for market extensions;
if a corporate-action lifecycle cannot be represented without parallel accounting,
record a failing conformance scenario and preserve the Python backend for that scenario.

Alternatives rejected: rewriting the existing Python simulator in Rust would duplicate
matching/accounting; silently extending v1 result fields would break the pinned runtime
validator. Use additive v2 engine wire types and a new opt-in runtime job version.

## Deliverables and staging

1. Pure target-weight sizing: decimal equity, quantities, explicit information-as-of
prices and lot sizes; floor long-only targets, sell before buy, reserve cash and fees,
no future prices. Produce deterministic quantity intents and residual cash/weights.
Expose as an independent library/CLI utility, with a platform adapter.
2. Session ledger: engine_request.v2 declares currency (USD/CNY), initial cash,
instruments, ordered sessions, explicit UTC open/valuation boundaries and precomputed
intents. Run upstream streaming batches, extract cash and holdings after each session,
mark only that session's complete valuation quotes, and end upstream explicitly.
Produce engine_result.v2 with final snapshot, per-session positions/cash/nav/costs,
actual orders/fills and request-linked intent identities. Every day reconciles.
3. Market constraints: explicit unit/board lots, long-only cash, T+1 sellable quantities,
caller-supplied suspension/listing state and side price-limit flags at each quote.
Use caller-provided session calendar rather than infer holidays or universal board rules.
Reject forbidden submissions through upstream denial APIs, without fake fills.
4. Capacity and accounting extension audit: use upstream quote-size liquidity consumption
and IOC only after tests demonstrate shared-side capacity and remainder cancellation.
Assess public upstream corporate-action adjustment APIs against record/ex/pay/release,
raw/adjusted price and fractional-share scenarios already present in the platform.
5. Opt-in consumers: runtime adds versioned protocol verification/publication for v2
without changing v1-v5 fingerprints. Platform adds pure target sizing / result adapter
and matched synthetic conformance evidence, preserving old namespace and defaults.

## Constraints and validation

Pin Nautilus 0.66.0, Rust >=1.99.0; exact decimal strings; immutable request data;
unknown fields/unsupported capabilities fail. Price data must have declared raw/adjusted
basis. No rates, exchange calendars, lot rules or historical tax assumptions are guessed.
Whole-repo required checks and independent review precede PR delivery. Merge provider
before consumers; record exact tested revisions, source trees and outstanding semantic
limits. Public records contain synthetic inputs only.

Key failure cases: equal-time/future information; missing/stale valuation; same-session
sell after a buy; overselling old lots; blocked trade retry policy; fee-inclusive cash;
partial fills consume shared capacity; zero-trade sessions; fractional entitlements;
corporate-action receivables; result tampering; old protocol compatibility.

## Completion boundary

Complete each independently verified deliverable in dependency order. Never describe
unrepresented corporate-action or evidence semantics as completed. A blocked scenario
must include a concrete reproduction/API evidence and a retained supported backend,
so future work is technically bounded instead of an untested capability claim.
