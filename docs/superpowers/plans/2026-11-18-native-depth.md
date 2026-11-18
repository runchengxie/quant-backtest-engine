# Native depth execution and onboarding plan

Execute inline. User approved advancing the remaining L2 product integration and account-feedback loop, then requested a plain-language README with technical material under docs and event-level support using available data.

## Design

Add a distinct versioned native depth request/result and opt-in product provider. Nautilus 0.66.0 remains the sole execution/accounting owner. Normalize ordered snapshots/price-level deltas into upstream L2 events; preserve event/available clocks and sequence. Supplied limit orders, cancels and bounded target-position decisions execute at declared eligible events. Target decisions read actual upstream holdings, cash and working orders. Keep all v1/v2 contracts and historical checkpoints unchanged.

Input explicitly declares event semantics and units. Market-by-price depth carries aggregate level quantities; historical order identities/queue calibration require separate evidence. Validate whole inputs, chronological order, identity, precision and snapshot initialization before engine mutation. End-of-run must include an explicit observation horizon so configured in-flight commands can be observed. New capability identifiers apply only to the new provider.

Inspect retained event-data inventory read-only. Produce a normalization/eligibility assessment in external task data, without publishing raw inputs or changing authoritative data aliases. Pair concise English/Chinese READMEs; move detailed capability and acceptance explanations into existing docs. README claims follow verified implementations.

## Tasks

- [x] Implement native depth contracts, adapter and hand-oracle tests for multi-level fills, order/cancel delay, cash fees and account-feedback targets.
- [x] Add strict SDK/profile validation, content-pinned client and opt-in product backend with actual raw-result evidence.
- [x] Review retained owner inventory metadata and record admission gaps externally. Raw replay deferred because instrument units, canonical identity and cross-stream order remain uncertified.
- [x] Rewrite paired READMEs for newcomers and align technical/acceptance docs.
- [ ] Validate regular wheels, required native/core/ownership/site gates, publish PR, merge, verify exact live revision and clean only this task.

## Execution evidence

Native depth tests cover multi-level fills, partial-fill targets, cancel races,
positive-delay arrivals between sparse observations, exact-cash rounding,
in-flight cash reservation and equal-clock ordering. SDK tests include real
binary calls, cancel-before-insert and independently corrupted evidence.
A bounded independent financial review reproduced the arrival and rounding
fixes and found no remaining blocker after the cancel-receipt regression fix.

The metadata review read existing owner summaries and semantic records only.
It read no new raw rows, rehashed no archives and changed no shared aliases.
Historical queue position and fifty-million capacity remain separate gates.

Language ruling: use Rust for new native execution and TS/Astro for the website.
Retain Python SDK/product boundaries and existing research/financial owners;
future financial transfers require arithmetic and checkpoint compatibility.
