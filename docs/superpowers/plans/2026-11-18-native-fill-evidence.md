# Native fill evidence and retirement implementation plan

> Execute inline with superpowers:executing-plans. The owner approved archival, per-fill Rust parity and performance measurement on 2026-11-18.

**Goal:** Archive the historical tutorial branch and supply exact native per-fill matching evidence with measured migration priorities.

**Architecture:** Preserve `OrderBook.apply_order` and `replay` legacy tuple contracts. Add `apply_order_with_fills` returning the aggregate plus ordered individual fills from the same Rust matching pass. Python `MatchingEngine` converts these to existing `Trade`/`Fill` values. Python remains the independent oracle. No new account ledger, production switch or optimizer replacement.

**Tech stack:** Existing Rust/PyO3, Python 3.12/3.13; no new dependencies.

## Tasks

- [x] Verify clean historical worktree, push annotated archive tag at 4820af3, verify remote target, retire only that branch/worktree.
- [x] Write failing multi-price, FIFO, partial/cancel, sell and randomized parity tests; prove old wheel lacks detailed API.
- [x] Add shared Rust fill capture, additive detailed API and typed stub. Adapt Python through explicit detailed method, preserve legacy aggregate/replay behavior; test immutable prior results.
- [x] Add reproducible synthetic benchmarks for Python/Rust per-order matching, batch replay and repeated independent paths. Check equal outputs before timing, record revision/environment/workload and medians externally. Do not generalize synthetic timings to market capacity.
- [x] Update paired scope docs, archive retirement record and ownership ledger. Preserve historical fixtures and checkpoint identity.
- [ ] Build/install fresh native/Core wheels externally, run installed microstructure and full core tests, type/lint/native/docs gates. Independent final review, exact-head CI, merge, publication verification and cleanup own task.

## Review focus

- Same-price FIFO and multi-level fills retain exact counterparties and execution prices.
- Legacy tuple callers and batch replay retain their outputs.
- No fills for no-trade/nonpositive input; partial remainder and cancellation match Python.
- A detailed result is a snapshot, unaffected by later order mutation.
- Native capability is explicit; missing old-wheel detailed support must not silently lose evidence.

## Validation ledger

RED: three new installed-old-wheel tests failed on absent detailed API/evidence. GREEN: 81 microstructure cases passed with a real native extension. Full installed Core: 1044 passed, seven skipped (native-absent profile cases and engine-dependent cases); the engine-dependent cases are validated separately with the real executable. Installed no-native profile: 51 passed, 30 optional native skips. Mypy: 112 files passed. Native and main Rust fmt/clippy/tests and README depth example passed. Ownership 17 passed. Strict site: 147 HTML, 206 artifact files, legacy anchors preserved. Independent read-only review approved; corrected its one stale docstring finding.

Measurement: 10,000 events, eight sequential independent paths, five repetitions; exact complete Python/native parity before timing and every sample. Initial local medians show a modest public-call gain in matching/replay and no gain in sorting. Keep NumPy/SciPy interfaces and Python orchestration; prioritize profiling allocations/boundaries over broad rewrites. Final committed-source measurement and delivery receipt remain external.
