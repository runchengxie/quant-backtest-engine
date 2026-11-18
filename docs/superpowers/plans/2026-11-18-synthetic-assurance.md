# Synthetic assurance and native lot planning

Execute inline with executing-plans. The user requested every synthetic validation proposed in the conversation, further Rust migration and website polish. Website presentation is a subsequent independent task after this provider merges.

## Design and constraints

Use existing financial owners. Preserve Python planning/impact/session APIs and all historical wire/checkpoint contracts. Introduce an opt-in Rust buy-only finite lot oracle with canonical decimal strings, explicit precision/range/state budgets and deterministic lexicographic ties. This is planning arithmetic, not a new execution ledger. Retain Python Fraction enumeration as the independent migration reference. No new Rust dependency.

A bounded native domain (1–16 assets, at most 100,000 states, decimal scale at most four for inputs, bounded prices/targets/quantities) keeps exact decimal objective/fee products representable. Reject unsupported input; never silently round or fall back. Report request digest, exact spent/objective strings, candidate feasibility/gap and exhaustive scope. Wire execution through the content-pinned SDK.

Synthetic assurance must exercise independent expected economics, not mirror implementation internals. Cover finite optimizer gaps, native order/account invariants, partial-fill/cancel/replan decisions, impact splitting/decay/round trips, path isolation/reproducibility/PIT boundaries and capital/liquidity stress at CNY 20m/50m. Capital experiments are assumed-market stress, not market capacity estimates. Store retained outputs externally.

## Tasks

- [x] Native oracle: red hand-oracle tests; exact bounded implementation, new `plan-lots` CLI and synthetic fixture; green native tests.
- [x] SDK boundary: strict request/result evidence, regular installed acceptance and deterministic cross-language Fraction parity across generated small domains.
- [x] Assurance: deterministic multi-seed account/latency and optimizer cases, independent impact properties, path state/PIT/seed tests and bounded stress report generator with provenance.
- [x] Documentation: paired scope, reproduction commands, remaining calibration gates, ownership migration ledger and historical method-pages audit.
- [ ] Full required checks, one bounded independent whole-branch review, exact-target CI, merge, task cleanup.

## Review focus

- Decimal products, accumulated objective and tie selection remain exact at supported boundaries.
- Search budgets reject before expensive enumeration; invalid candidate cannot produce a gap.
- Pending orders reserve cash/shares and fill observations remain causal under repeated equal clocks.
- Synthetic stress claims remain separated from calibrated liquidity/impact/capacity.
- Historical Python owners/fixtures retain their source provenance and unchanged numerical contracts.

Review ruling: independently prove native optimality and lexicographic ties in the SDK using scale-eight integer enumeration. The bounded extra verification cost is explicit; direct Rust callers execute only native planning. Suboptimal and nonlexicographic forged results were observed failing before the fix and rejected afterward.
