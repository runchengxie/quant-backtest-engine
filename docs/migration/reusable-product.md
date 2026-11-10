# Reusable product ownership and migration gates

[简体中文](reusable-product.zh-CN.md)

Core 0.3.0 source now includes the complete independent daily financial graph and explicit
python.daily backend alongside the minute, planning and scenario owners. SDK 0.3.0
retains its standard-library namespace. Provider B and Platform B are released at the
revisions recorded in the ownership registry; provider C review, merge, exact merged
wheels and Platform C cutover remain pending. Use [installation](../product/installation.md),
[backend limits](../product/backends.md) and [daily inputs](../product/daily-inputs.md).
Source implementation is distinct from release and consumer evidence.

## Current implementation and pending consumers

| Component | Current implementation | Release / next ownership gate |
| --- | --- | --- |
| Engine Rust | 0.2.0, NautilusTrader 0.66.0; unchanged native quote/session/CLI behavior | Python capabilities do not extend Rust; upstream execution/accounting remain authoritative |
| Engine SDK | `quant-backtest-engine-client` 0.3.0; `quant_backtest_engine`; Python ≥3.11; standard-library product contracts | Pin the exact reviewed source and verified wheel; base SDK never imports core |
| Optional Engine core | Core 0.3.0 source; Python 3.12/3.13; independent daily, minute, planning and scenario owners | Provider C review/merge/exact merged artifacts pending |
| Platform | Consumer B retained | Consumer C (Task 15) follows merged verified provider C; research/publication remain Platform |
| Runtime | Existing 0.1.0 and v1–v8 paths retained | Optional additive v9/0.2.0 consumer follows merged provider and operational acceptance |

Core base depends on SDK `>=0.3.0,<0.4`; repository builds and consumers pin an exact
merged VCS revision or verified wheel hash. Local invocation is explicit. No PyPI
publication is required. Package versions never substitute for source, executable,
dependency, contract or checkpoint identity.

## Historical M0 baseline — 2026-11-09

At M0, Engine Rust was 0.2.0, SDK was 0.2.0, Platform was 0.0.1 and Runtime was 0.1.0.
No Python financial implementation had transferred and the optional core was not yet
implemented or released. This dated baseline explains the original inventory; it does
not describe the current provider A implementation above.

The inventoried source revisions are Engine
[`c65548a`](https://github.com/runchengxie/quant-backtest-engine/tree/c65548a4ee1e938125cce1edbcc282c760c4c8f2),
Platform [`7a618bd`](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355),
and Runtime [`01ed4c3`](https://github.com/runchengxie/quant-backtest-runtime/tree/01ed4c34f955ef6cd39d13aa073b6d61b610d321).
Design PR 20 merged as
[`c5cbb88`](https://github.com/runchengxie/quant-backtest-engine/commit/c5cbb885a6abb90b7cc6b41e111be71bd8b41069).
These are historical source observations, not certification of the current release or live deployment.

## One financial owner

Each run has one financial owner; each scenario has independent accounts and state.
Rust continues using upstream Nautilus accounting. The optional Python minute provider owns
its extracted financial state. Engine will not import Platform, Runtime or
private research at runtime in the completed product. A temporary compatibility
provider must be explicitly supplied and registered with a removal gate; it cannot
pass standalone acceptance.

Engine's approved scope includes deterministic sessions/checkpoints, execution
costs and impact, supplied market paths, backtest-specific planning, reservations,
allocation and result evidence. The minute closure moves together: minute/session,
checkpoint/impact/quantity locks, matcher state/validation, capital flows, corporate
actions and valuation events. Stateful classes switch only with that whole cohort.

General factor/risk estimation, model training, selection, generic signed/sparse
optimization and research admission/publication stay Platform. Engine accepts their
explicit inputs or public optimizer callbacks. Daily execution must first separate
selection, metrics, provider calendar fetching and publication. Deterministic
microstructure matching must separate eager training imports; its optional PyO3
extension is distinct from Nautilus. Runtime retains queues, job/attempt identity,
leases, supervision, resource limits, durable admission and publication. Engine
financial checkpoints do not absorb Runtime's database responsibilities.

## Gates and executable acceptance

| Wave | Delivery and stop condition |
| --- | --- |
| M0 | Freeze source, alias, route and consumer inventory; independently review this ownership record |
| M1 | Add SDK contracts and optional core runner; explicit backend, exact clocks, old SDK/CLI behavior preserved |
| M2–M3 / A | Closed leaf and minute/session extraction; independent installed wheels, full ledger/restore parity and bilingual mechanism docs before Platform A switches |
| M4 / B | Matching, account feedback, supplied optimizer protocol, bounded planners and independent scenarios; optional dependencies and prefunding/actual-fill evidence before Platform B switches |
| M5 / C | Neutral daily inputs/calendar/summary followed by full financial graph and golden ledgers; Platform C retains construction and publication orchestration |
| M6 / R | Fixed additive Runtime provider and real process-kill/admission tests; representative consumers validated against exact merged provider pins |
| M7 / T and delivery | Preserve and regenerate the eight-scene tutorial, then verify installed profiles, bilingual live pages and task-only cleanup |

Every wave delivers implementation, tests, canonical English documentation and its
Chinese counterpart before a consumer switches. Providers merge and produce
verified artifacts first. Preserve arithmetic, rounding and model semantics during
extraction; capability changes require separate conformance. Failed consumer gates
keep the old path/default or an explicitly pinned legacy environment.

## Registry and historical routes

The [machine-readable registry](reusable-ownership.json), schema
`engine-ownership.v1`, records each module/symbol's old and planned owner, provider
version, source revision, old/new locale URLs and anchors, compatibility path,
wave/gate, removal condition and named executable acceptance command. It also
records source/doc clusters, all inventoried public legacy aliases, retained or
split owners and public consumer API shapes. Exact private files stay in private
task data; this ledger does not authorize editing unrelated consumers.

`status: planned` permits a null source revision and future files/tests/routes.
`status: implemented` requires an actual full reviewed source revision present in
Git, provider files at that revision and in the tree, and existing paired Engine
docs. Release/deployment availability is recorded separately after provider merge;
never use a placeholder hash or a self-referential commit to suggest availability.
The checker does not certify financial semantics, review approval or live URLs.

Historical locale declarations are explicit. For example Platform's
`guides/minute-execution.en/` is English and `guides/minute-execution/` is Chinese;
its destinations are Engine's `guides/minute-execution/` and
`guides/minute-execution.zh-CN/`. Preserve `.en`, `.en-US`, unqualified Chinese and
`.zh-CN` spellings. Several symbols may share one old page and one destination;
conflicting mappings fail. A source with no Chinese page gets a new Chinese
companion, not an invented historical Chinese URL. After a provider publishes,
Platform's old pages become short locale-correct notices with stable anchors;
keep old source links and dated receipts at their original revision.

Keep compatibility aliases for **at least two minor-release cycles and until every
recorded supported consumer has migrated**. Removal also requires release notes,
doc-link migration and tests. Static import counts are not a deployed-consumer or
retirement inventory. Consumer cohorts include minute/actions, account recovery,
pending feedback, bounded planning, daily/position adapters, runtime clients,
independent signal-acceptance replay, market-research minute/daily/actions, and
workbench import checks. Each needs validation or an explicit full pinned legacy
route before cutover. An internal minute import needs a supported public replacement.

Old checkpoints remain with their original exact provider/release and full
Runtime/Go executable/dependency closure. No transparent cross-owner or cross-backend
restore is promised. Never request a new checkpoint from a failed financial owner.

## Preserve the reviewed tutorial

[PR 19](https://github.com/runchengxie/quant-backtest-engine/pull/19) at
[`4820af3`](https://github.com/runchengxie/quant-backtest-engine/tree/4820af3b82940e7697cb8c92154315b1d59ee23d)
remains preserved, unmerged reviewed source. Retain all eight scene identifiers:
`selection`, `paths`, `cost`, `impact`, `lots`, `flow`, `book`, `risk`. Keep bilingual
catalogs/pages, exporter/helper sources and hashes, exact-clock projection,
no-JS financial tables, replay/DOM/fixture tests and license/source history.

Its current financial fixtures bind actual Platform owners. Do not relabel them
as newly implemented Engine mechanisms. At each transfer, update typed-call
allowlists, class/module bindings, owner labels, revisions/URLs and every executed
helper/source hash; regenerate only from clean merged providers and locked optional
environments. Keep old provenance. Risk/null teaching can retain Platform as a
separate optional analytical owner. Replace the forced Runtime documentation-only
checkout with an optional versioned reference when integrating. Browser replay
continues displaying exported owner results; it never computes a financial model.
This M0 change leaves the tutorial branch and worktree intact.

## Validate this record

```sh
python -m unittest project_tools.test_reusable_ownership -v
python project_tools/check_reusable_ownership.py
mkdocs build --strict --site-dir "$TASK_DATA/site"
python project_tools/check_docs.py --site-dir "$TASK_DATA/site"
git diff --check
```

Use the locked documentation environment and an external task-data output directory.
The checker is read-only and never executes registered acceptance commands.
Future financial gates live in the approved implementation plan under
`docs/superpowers/plans/2026-11-09-reusable-backtest-product-implementation.md`.
Public examples remain synthetic. No broker/order, production configuration,
scheduler, real cost calibration or new data-acquisition work is included.


## Pure period-leg financial closure (Task 15P)

Task 15P closes a pure-source omission discovered after provider C PR #24. Explicit-input leg construction, state rollover, supplied participation lookup, period aggregation and the separate legacy trade accounting APIs move to Core 0.3.0 unchanged. Every period field/default and the owned CostBreakdown identity remain; unknown diagnostics stay unknown and costs aggregate once. Selection, weight construction, research projection/metrics and orchestration remain Platform. Diagnostic long/short periods add no daily cash, borrow or margin capability. [Exact APIs, compatibility semantics and evidence](../guides/diagnostic-close-replay.md) describe the boundary. Review/merge and exact follow-up artifacts precede Task 15 consumer resumption, then Astro Task 19; versions alone are not source identity. No PyPI publication.
