# Reusable backtesting product: architecture and staged ownership transfer

Status: proposed design for owner review, 2026-11-09. The owner selected the direction: Engine becomes the independently reusable backtesting product, with an optional Python implementation and the existing Rust execution backend. This document makes the interfaces, migration boundaries and acceptance gates concrete. No implementation migration is authorized by this document's publication.

Owner approval: the owner instructed execution of this concrete design on 2026-11-09. The proposed status above is the historical review state. Implementation is now authorized through the staged plan and its compatibility/review gates; production/broker boundaries remain unchanged.

[简体中文](2026-11-09-reusable-backtest-product-design.zh-CN.md)

## 1. Outcome and chosen approach

A new project can install a documented Engine variant, supply explicit data and policy inputs, run a backtest and inspect supported economic evidence without installing Platform, Runtime or private research code. Basic Rust quote replay remains lightweight. Rich Python financial sessions and scenario/planning modules are optional Engine-owned packages. Runtime is optional operational infrastructure.

| Approach | Tradeoff | Decision |
| --- | --- | --- |
| Rename/move files or wrap Platform behind Engine | Quick facade, but preserves hidden dependencies, ownership ambiguity and cycles | A temporary explicitly registered compatibility adapter only; never the completion criterion |
| Rewrite all algorithms and accounting in Rust | Large simultaneous semantic/performance change; upstream does not support every current Python rule | Separate later capability work, not the migration prerequisite |
| Engine-owned product interfaces plus staged Python extraction and explicit backends | Preserves tested economics while gaining independent installation and coherent ownership | Selected direction; concrete defaults below remain reviewable |

Success means independently installed executable behavior, not merely an import, common function name or reorganized website. Financial migration and documentation migration are the same delivery unit.

## 2. Current evidence and boundaries

Inspected source revisions:

| Component | Revision | Current surface |
| --- | --- | --- |
| Engine | c65548a4ee1e938125cce1edbcc282c760c4c8f2 | Rust library/CLI; quote request v1, session request v2, sizing and session stream; fixed Nautilus 0.66.0 adapter |
| Platform | 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355 | Python minute/session/accounting cluster, impact, market paths, execution planning, costs and allocation; broader factor/research tools |
| Runtime | 01ed4c34f955ef6cd39d13aa073b6d61b610d321 | Go lifecycle/durable admission; fixed Python financial adapter; v1-v8 jobs |
| Unmerged tutorial | Engine PR 19, 4820af3b82940e7697cb8c92154315b1d59ee23d | Eight bilingual synthetic replay scenes, owner exporter, exact no-JS tables and tests; source approved, not a released product capability |

Current EngineClient is the zero-dependency quant-backtest-engine-client distribution, import quant_backtest_engine, Python >=3.11. Its validated results and both Runtime validators require the exact Nautilus backend/version. The Rust static validator validates quote request v1 only. Rust session streaming does not restore a financial snapshot. Existing corporate-action conformance demonstrates an upstream basis-adjustment mismatch; an API wrapper cannot create that missing capability.

Platform requires Python >=3.12. Its ticknet package initializer eagerly imports dataset/model code, including training dependencies, even for matching imports. MinuteSession depends on the internal minute/actions/valuation/capital cluster. Sleeve allocation depends on execution-integrity analytics. These dependencies must be resolved before standalone extraction is claimed.

Runtime financial resume v8 binds the exact installed Platform revision, loaded financial sources, configuration, tapes and dependency versions. Moving source paths changes that identity. Old v8 checkpoints cannot silently become checkpoints of a newly packaged Engine provider.

Source anchors: Engine src/{contract,session_contract,validation,sizing,session_stream}.rs and python/src/quant_backtest_engine/client.py; Platform packages/platform/src/quant_platform/{backtest,_portfolio,portfolio,analytics}; Runtime src/backtest_runtime/{financial_sessions,financial_session_adapter,engine_sessions_protocol}.py and internal/{protocol,app,store}.


Source references: [Engine](https://github.com/runchengxie/quant-backtest-engine/tree/c65548a4ee1e938125cce1edbcc282c760c4c8f2), [Platform](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355), [Runtime](https://github.com/runchengxie/quant-backtest-runtime/tree/01ed4c34f955ef6cd39d13aa073b6d61b610d321), [preserved tutorial PR 19](https://github.com/runchengxie/quant-backtest-engine/pull/19).

## 3. Target ownership and dependency direction

~~~mermaid
flowchart LR
    A[Other projects] --> E[Engine public API / CLI / SDK]
    P[Platform research and analytics] --> E
    R[Optional Runtime job supervisor] --> E
    D[Caller supplied market and model artifacts] --> E
    E --> C[Contracts / capabilities / results]
    E --> S[Scenario and execution-planning modules]
    E --> B[Explicit backend interface]
    B --> N[Rust / Nautilus backend]
    B --> Y[Optional Engine-owned Python financial backend]
~~~

Engine owns public backtest contracts, deterministic execution/session state, costs and impact used by execution, scenario orchestration and backtest-specific planning. Each run has exactly one financial owner. Different scenarios have independent accounts and state.

Platform retains factor construction, training, feature pipelines, general factor-risk estimation, retrospective statistical risk calibration, portfolio research and broader analytics. It supplies forecasts/risk snapshots/planners through public interfaces and consumes Engine results. Private strategy selection, hyperparameters, promotion decisions and the authoritative research trial registry remain outside Engine.

Runtime retains queues, job/attempt identity, leases/tokens, process supervision, resource limits, fsync/rename/SQLite admission and final publication. Engine supplies deterministic financial checkpoints; it does not need Runtime's database for local stepping or restore.

The completed target has no runtime import from Engine into Platform, Runtime or private research. During migration, an optional compatibility provider may be supplied explicitly by a consumer. It is a declared intermediate dependency, has a removal gate and is not part of the standalone Engine acceptance environment.

## 4. Packages and supported installation profiles

Proposed new package/module names are design placeholders until packaging checks reserve final names. Do not overlap installed files across wheels.

| Profile | Ownership and dependencies | Acceptance |
| --- | --- | --- |
| Existing transport SDK | Keep quant-backtest-engine-client and quant_backtest_engine ownership/API; Python >=3.11, standard library | Existing sizing/session calls and installed-wheel tests remain valid |
| Rust execution | Existing Engine executable/library; preserve current experimental target/release limitations | Current quote/session/CLI and upstream accounting conformance |
| Product runner and Python reference modules | New Engine-owned distribution, proposed quant-backtest-core / quant_backtest_core; Python >=3.12 initially; base depends only on the lightweight Engine SDK, while minute/scenario/planning dependencies are explicit extras | Base runner imports without scientific/training packages; installed minute extra runs financial sessions without Platform/Runtime/private packages |
| Optional optimization/scenarios | Engine-owned optional dependencies; exact numerical/solver requirements declared | Base SDK and ordinary docs do not acquire solvers, Torch or model-training dependencies |
| Optional microstructure | Extract simulator/orderbook dependencies from eager training imports; native acceleration remains explicit | Matching imports and runs without Torch/training packages; Python/reference parity retained |
| Runtime integration | Separate consumer, optional installation | Direct Engine use works with no queue/database/service |

Keep the existing SDK namespace with its existing distribution. Use a distinct namespace for the extracted Python core rather than two wheels writing quant_backtest_engine files. The product client can expose optional local operations through a documented lazy integration, but its base import/install must stay independent.

Product manifest/result DTOs and capability descriptors are additive standard-library modules in the existing SDK distribution. The core depends on that public contract surface. The SDK base does not import the core; optional local-product invocation is explicit. The full local runner and the proposed quant-backtest CLI live in the new core distribution. The existing Rust executable remains a supported low-level backend/tool, with its old commands unchanged. A full product caller uses the product runner; a basic existing caller can keep the SDK/Rust-only path. The provisional product operation run-manifest is exposed by the product CLI, not silently added to the old Rust command semantics.

The first certified environment is the existing Linux target and tested Python versions, not an invented cross-platform guarantee. Validate Python-core 3.12 and 3.13 explicitly; preserve SDK 3.11 compatibility. Published main, downloadable binaries and installed wheel versions are distinct availability states.

## 5. Public product interfaces

These are proposed interfaces, not current command names. Preserve existing run/size/capabilities/session-capabilities/validate/session-stream behavior. Add a versioned product operation, provisionally run-manifest, rather than changing old wire meanings.

A local library and CLI consume the same product manifest:

- Product schema and explicit execution backend id.
- Required semantic capabilities and selected contract/model versions.
- Input artifacts or small inline inputs, byte hashes, currencies, raw/adjusted share basis, calendar/timezone, units, availability/information/decision/entry/effective/report/valuation clocks.
- Initial account and state, fully resolved execution/fee/impact settings and all external tapes, including explicitly empty tapes.
- Policy/forecast/risk references, availability and state versions; explicit scenario family, seed, transformations and fixed-versus-recomputed forecast mode.
- Output location supplied by the caller and provenance for all actual providers/configuration.

Market data ingestion and credentials remain caller responsibilities. Engine does not silently load a user's research configuration or fetch privileged data. Public examples are synthetic. Runtime applies its existing artifact/resource boundaries to job execution.

The public product envelope uses explicit decimal strings for monetary transport and string-safe UTC nanosecond clocks. Existing native v1/v2 integer-clock contracts remain unchanged; exact adapters perform conversion without JavaScript-number intermediates. Native floating-point calculations retain their declared arithmetic/rounding; serializing a result as a decimal string does not create decimal-exact economics.

Backend descriptors declare backend/provider/source/dependency identity, supported input/result/checkpoint versions, semantic capabilities, units and restrictions. Backend selection is explicit. Unsupported semantics or missing optional packages fail before financial execution. There is no silent Rust-to-Python fallback or claim that a product's union of capabilities belongs to every backend.

A reviewed fixed provider registry may resolve installed backend identifiers. Requests cannot name arbitrary Python imports, executable commands or serialized code. Trusted local applications can pass an explicitly constructed policy object; remotely resumable jobs use registered versioned policy factories and supported state formats.

## 6. One account owner and honest results

The Python backend initially preserves the extracted financial implementation. The Rust backend continues to use upstream accounting. Do not add a second cash ledger to make unsupported upstream behavior appear to work.

The product result envelope contains the supported economic tables plus explicit unavailable evidence:

- Order intents, admission/rejection/cancellation state, actual fills and cash fees.
- Economic cash/positions, available/locked/sellable quantities, reservations and delayed visible reports.
- Corporate-action rights/receivables, payment/release, valuations and external capital flows.
- NAV/return basis and mark freshness; residual inventory and unknown realizable liquidation wealth.
- Scenario/input/provider/configuration identities, attempted/completed/failed states and partial evidence.
- Backend-specific original result reference plus a versioned normalization receipt.

Unknown is distinct from zero or an empty supported ledger. A completed computation does not mean every order filled or a strategy passed research admission. Canonical conversion must not claim execution-aware completeness for the current limited Engine adapter.

Impact already included in fill price is charged once. Cash fees are debited once. Benchmark/opportunity shortfall is descriptive and is not an additional debit. Deposits/withdrawals remain separate from PnL. Planned sale proceeds cannot finance unfilled buys.

The existing research-contracts package physically resides in Platform and contains broader promotion/publication semantics. Prefer a minimal Engine-owned execution-clock/result DTO and a Platform translator, or a separately published neutral dependency with proven installation closure; never require a Platform source checkout or copy research admission into Engine.

Move execution-integrity helpers with a neutral Engine result/evidence seam where needed; do not retain Engine -> Platform analytics imports. Retrospective risk-calibration statistics remain Platform analytics and can consume exported Engine evidence.

## 7. Costs, planning, scenarios and policies

Costs have pure estimate/quote and realized-charge interfaces with currency, side, effective clock, quantity/notional basis, minimums, tax and rounding semantics. Each backend lists the supported subset. Estimates and actual fees are reconciled, not assumed equal.

Impact retains explicit units, transient decay clock, nondecaying sensitivity, model state and checkpoint identity. Nonzero permanent/cross impact is not promoted to calibrated fact. Rust support is a separate implementation/conformance task.

Backtest-specific planning includes cash/reservations/sellability/locks/capacity and actual-fill feedback. Preserve the bounded transient-impact planner's conservative cash domain and the finite integer solver's prefunded search/optimality limits. General factor covariance estimation and research portfolio solvers stay Platform unless a later extraction has a concrete standalone consumer.

Scenario execution separates same-market execution perturbations from alternative external market paths. Both rerun independent accounts. External market changes must rerun all path-dependent features/predictions through caller-supplied interfaces, or be explicitly labeled a fixed-forecast sensitivity with that limited interpretation. Engine cannot silently reuse historical forecasts and claim a full alternative research history.

A local sequential scenario runner is sufficient initially. Runtime may schedule the same versioned manifests later. Do not add another scheduler, authoritative trial registry or private model-training implementation. Retain all attempted scenarios and failure metadata. Fixed reproductions are not new independent market observations.

## 8. Sessions and recovery compatibility

Expose a public session factory with step, immutable observation/report, checkpoint, restore with externally expected inputs/tapes/provider/model identity, and finish. Full financial state includes cash, positions, rights, pending reports/orders/reservations, locks, impact, policy, cursor and deduplication state.

A failed financial step invalidates the live session; retain original failure and last successful checkpoint. Do not request another checkpoint from a poisoned owner. Unsupported/missing tapes fail closed.

Separate three meanings:

1. Engine Rust session stream: provisional reports and prefix validation, no financial snapshot import.
2. Runtime v7 queued stream: its existing terminal-failure semantics.
3. Runtime v8 financial restore: admitted source-bound failed predecessor to a new token-owned successor.

New Engine packaging gets an additive provider/binding/job path. Existing Runtime v1-v8 and SDK validators retain their semantics, exact identities and golden fixtures. Never loosen Nautilus identity checks to admit an unrelated Python result.

Old checkpoints stay on their original pinned provider/release environment. Cross-producer or cross-backend restore is unsupported unless a separate explicit converter proves complete economic/state equivalence and source compatibility. Merely retaining minute-session.v2 as a string is not a migration.

The pinned legacy environment includes the full Runtime/Go executable and dependency closure, not just the old Platform wheel. This design promises a documented legacy restore/reproduction path, not transparent hot restoration by a changed worker. Operational cutover must route only supported job/provider/binding versions; an old worker must not blindly claim a new-version queue. If safe coexistence is not demonstrated, use an isolated legacy recovery environment and defer retiring the old release. No live job-store or production rollout is performed by this design task.

Engine owns financial state serialization and validation. Runtime continues to own durable candidate write/fsync/rename/admission/attempt fencing and publication; source compatibility does not bypass those controls.

## 9. Migration waves and stop conditions

Every wave includes code, tests, canonical English documentation and its Chinese counterpart before the consumer switches. Provider merges/releases precede consumers. Validate current combined provider/consumer revisions.

| Wave | Deliverable | Gate before advancing |
| --- | --- | --- |
| M0 Design approval | Adopt ownership/package/API decisions; inventory consumers/docs; preserve PR 19 | Owner review of this concrete design; update implementation plan and contributor rules only for approved scope |
| M1 Product seams | Add descriptor/manifest/result contracts and explicit backend/session interfaces; old APIs unchanged | Cross-language contracts; missing/unsupported backend rejection; exact legacy SDK/CLI behavior |
| M2 Leaf mechanisms | Transfer market paths, execution cost/impact primitives and required neutral integrity helpers into Engine-owned modules | Installed-wheel independent mechanism tests, source/config identity and old/new hand-oracle parity; no reverse imports |
| M3 Financial cluster | Transfer minute/session/account/actions/valuation/capital/locks/pending reports together; split pure matching from training imports | Every-boundary restore, fee/cash/share/entitlement conservation, fresh/stale/unknown wealth, minimal no-ML install |
| M4 Planning and scenarios | Transfer bounded execution-aware planners/allocation/finite exits and pure replay execution-impact estimation; compose independent scenario runs and external policy callbacks | Prefunding/capacity/feedback correctness; complete impact/admission tests and native missing-fill rejection; dependency closure without research/factor/training leakage; failure retention |
| M5 Daily replay disentangling | Transfer daily adjusted/ideal/capacity/sequenced/raw-share/fee/delisting execution after separating selection, research metrics, provider calendars and publication | Full daily ledgers and dated-fee/action conformance; neutral explicit calendar/target/result inputs; no provider login or Platform import |
| M6 Consumers and Runtime | Platform forwards to Engine owner; add a new fixed Runtime provider path; migrate representative independent consumers | Full affected consumers with exact new provider pin; actual process-kill/admission tests for changed Runtime paths; old v1-v8 stable |
| M7 Public product delivery | Coherent Engine docs/tutorial/releases, Platform compatibility pages and Runtime operations docs; clean install examples | Real browser EN/ZH/mobile/theme/keyboard/reduced-motion/navigation checks; source/asset/deployment identity; task-only cleanup |
| Later Rust parity | Add richer costs/impact/actions/restore only through supported upstream operations | Capability-specific independent conformance; never inferred from Python support |

No wave combines ownership extraction with an unreviewed arithmetic/rounding/model rewrite. Changed capability needs its own tests and version. Start with the smallest closed dependency slice and expand only after its independent installation gate passes.

Compatibility aliases in a migrated release refer to the same new class objects; this is not a promise of cross-release checkpoint or serialized-class identity. Old releases remain pinned for old artifacts.

Keep compatibility aliases for at least two minor-release cycles and until every recorded supported consumer has migrated. Removal requires a release note, doc link migration and tests; directory age alone is not a retirement condition. If a consumer gate fails, keep the old public path and default, fix the provider or use the previous version; never force a broken cutover.

## 10. Documentation moves with each implementation

For every transferred public symbol/package, the PR includes an ownership row: old module -> new owner/version -> old/current docs URL -> new EN/ZH URLs -> compatibility adapter -> removal gate -> executable acceptance.

Canonical Engine documentation will cover product/installation profiles, backend capability matrix, contracts/units/clocks, costs/impact, financial sessions/actions/flows, bounded planning, scenario meaning, recovery limits, result interpretation and an independent-project tutorial.

Platform retains its factor/model/risk/analytics documentation. Former backtest mechanism pages become short compatibility pages pointing to the new Engine owner after that provider and its corresponding documentation are published. Keep stable old URLs/anchors where practical; use a redirect/stub map and test both languages. Do not retain two complete maintained explanations of one moved implementation.

Runtime retains supervision/resource/job/admission/publication documentation. Its financial examples switch only with the new supported provider. Clearly distinguish prefix replay from snapshot restore and main features from released executable availability.

Preserve historical Git/source links, dated conformance results and original experiment receipts at their original revision. Add a current interpretation/owner link; do not rewrite old results to look produced by the new Engine package.

The existing eight-scene PR 19 tutorial, exporter, exact-clock projection, semantic catalogs and no-JS tables are retained as reviewed work. Rebase/incorporate them deliberately under the approved architecture; every scene continues to identify its actual implementation owner until transfer is complete. The earlier Platform-hosting choice is superseded for planning by the selected Engine-product goal; publication location and scope follow the approved ownership design. No page is discarded during this design task.

Corresponding README, API references, examples, capability/release matrices, navigation, locale registries, source links, doc checks and applicable AGENTS.md boundaries change in the same wave. Default English and Chinese companions remain aligned. Public assets contain no private conversations/account/strategy inputs.

### Concrete source and documentation migration map

The initial source closure for M3 is Platform backtest/{minute,minute_session,_minute_checkpoint,impact,quantity_locks}.py plus _portfolio/{minute_execution,_minute_state,_minute_validation,capital_flows,corporate_actions,valuation_events}.py under packages/platform/src/quant_platform. Preserve class identity through compatibility reexports. The account-events/paper-account/checkpoints family and pending-allocation optimizer protocol are separate optional M4 closures; do not drag generic signed research optimizers into the core.

The M4 pure replay closure also includes `ticknet.simulator.impact` (`ExecutionSchedule`, `ImpactResult`, `ImpactEstimator(session).estimate(schedule)` and `_mid`) at `packages/microstructure/src/ticknet/simulator/impact.py`, transferred to `core/src/quant_backtest_core/microstructure/impact.py` in Task 9. Preserve dataclass fields, units, child limit-order policy, validation/operation order and actual-fill/VWAP evidence, with standard-library imports and no Torch/Platform dependency. Carry all eleven original `tests/microstructure/test_impact.py` tests plus the two impact admission tests in `test_replay_clock.py` and `test_native_impact_estimation_rejects_missing_fill_evidence` in `test_rust_parity.py`; installed Python, real native-rejection and pinned-source parity evidence are required. Native estimation retains `NotImplementedError` before mutation because actual per-fill evidence is missing. Preserve raw empty-book midpoint/slippage sentinels and disclose their diagnostic limitation; a zero sentinel is not measured zero market impact, and descriptive displacement/shortfall is not another cash debit.

Engine's simulator extraction covers six pure implementation modules (`matching,pack,ordering,replay,correctness,impact`) plus lazy `__init__`, not all nine legacy files. Task 12 supplies thin identity aliases for the moved classes, including all three impact classes and supported lazy exports. `generator.py` remains a learned-model concern; `sqrt_law.py` remains a supported consumer/diagnostic using the generator and estimator until broader ownership is decided. Retain their integrations and legacy routes; do not copy/delete them under a blanket Engine extraction or advertise the diagnostic as an implemented calibrated square-root market law.

For M5, daily execution_sim reporting currently imports research metrics, position replay mixes holding selection and simulation, and execution calendars can fetch provider data. Introduce execution summary DTOs, explicit targets and supplied calendar artifacts before moving that financial implementation. Keep factor IC analysis, top-k selection and provider authentication with their actual external owners.

| Current Platform documentation | Canonical Engine destination after the corresponding wave |
| --- | --- |
| backtest/market-paths.md and .zh-CN.md | Same backtest/market-paths pair with M2 scenario mechanism |
| backtest/minute-session.md and .zh-CN.md; guides/minute-execution.en.md and its Chinese original | Engine backtest/minute-session pair and guides/minute-execution pair with M3 |
| backtest/transaction-cost-evidence pair; analytics cost-scope explanations | Engine cost/evidence guide with M2/M4; explicit statistical limitations retained |
| [Legacy replay-impact source](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/packages/microstructure/src/ticknet/simulator/impact.py); no historical documentation route | Engine `docs/microstructure/impact-estimation{,.zh-CN}.md` with Task 9 code/tests; add actual reviewed code SHA and implemented/unreleased ownership evidence in that transfer, not this amendment |
| concepts/impact-planning and discrete-inventory EN/ZH pairs | Engine same-topic optional-planner guides with M4 |
| backtest/sleeve-allocation pair; execution-integrity/paper-account/account-feedback/capital/reconciliation guides | Engine execution allocation/account/evidence guides with M3/M4; add missing Chinese product companions |
| contracts/pending-allocation; signed/sparse optimization guides | Split execution reservation contract into Engine; generic optimization documentation stays Platform |
| execution-simulation/sequenced-execution/corporate-action/dated-fee/backtest-output guides | Engine mechanism/result guides after M5; Platform retains target-construction and analysis workflows |
| backtest/risk-calibration pair and factor-risk/model guides | Remain Platform; Engine links to the separate public analytical owner |
| Platform install/API/entry-point/overview and ownership maps | Remain Platform, updated as consumer documentation and compatibility pointers |
| Runtime financial-sessions/session-stream/queued-sessions/ownership guides | Remain Runtime, updated with the actual new provider and unchanged durable job responsibilities |

Preserve existing .en, .en-US, unqualified Chinese and .zh-CN old routes through an explicit locale-aware map. Do not assume all unqualified existing pages are English. Add current tested combinations beside historical matrices; do not replace old tested revisions or equate main with an alpha release.

PR 19's exporter currently imports allowlisted quant_platform types and binds those class/module source hashes. Update the typed-call allowlist, owner revisions/URLs and every executed exporter/helper/source hash with each transfer, then regenerate from clean merged providers. Retain previous fixture provenance as historical evidence. Its required Runtime checkout only hashes a documentation file; replace that build dependency with an optional versioned documentation reference. A retained risk/null teaching scene may still use Platform as a separate optional analytical owner, without making Platform a runtime dependency of Engine.

## 10.1 Static product frontend and retained reference

`web/` contains an Astro static frontend. React is the only client component framework. Astro renders product navigation, explanations, evidence boundaries and complete result tables at build time. React islands provide event playback, synchronized charts and preset controls. Ordinary builds consume committed public synthetic artifacts and need no running server, broker, Platform checkout or Runtime service. Dependencies, Node engine and package-manager version are pinned in `web/package.json` and its lockfile after compatibility verification, not selected from an assumed framework major version.

MkDocs continues rendering existing technical references and the preserved eight-scene tutorial. Its support for JavaScript is not in question: Astro is chosen for maintainable components and shared interaction state. No Starlight migration or blanket `/docs/` move is part of this task. The boundary follows [Astro islands](https://docs.astro.build/en/concepts/islands/); deployment configuration follows the [official Pages guide](https://docs.astro.build/en/guides/deploy/github/). The assembly choices below are this project's design, not behavior supplied by Astro.

## 10.2 Homepage, route and asset ownership

All paths in this section are relative to base `/quant-backtest-engine/`; the production origin is `https://runchengxie.github.io`. Astro uses static output and trailing slash directory routes. Local acceptance must serve the same base, not merely `/`.

| Public output | Owner and behavior |
| --- | --- |
| `/`, `/index.zh-CN/` | Astro product home, EN and Chinese respectively; retain the full corresponding MkDocs-rendered overview article and old heading IDs in the page, below the new product introduction. Existing source stays `docs/index{,.zh-CN}.md`. |
| `/reference/`, `/reference/zh-CN/` | Astro reference navigation landing, linking to the actual unchanged MkDocs paths. No duplicate reference text. |
| `/learn/`, `/learn/zh-CN/` | Astro learning overview, eight scene cards with conclusion, source class, evidence stage, sample scope and open question. |
| `/learn/{scene}/`, `/learn/zh-CN/{scene}/` | Astro explanation and complete static tables for each of `flow,book,impact,cost,lots,paths,selection,risk`. |
| `/lab/{scene}/`, `/lab/zh-CN/{scene}/` | Astro focused synchronized replay of the same artifact; explanations link to `/learn/`. |
| All other existing HTML paths, including `/backtesting-explained/` and `/backtesting-explained.zh-CN/` | MkDocs, unchanged public paths and anchors. Preserve `tutorial`, `contracts`, `migration/...`, `.zh-CN` and every subsequently added technical route. |
| `/_astro/**` | Astro bundles, exclusively. |
| `/assets/learning/**` | Committed public trace, manifest, source records and catalog projections, copied by the assembly owner. Astro may consume but may not emit duplicate copies. |
| `/assets/method/**`, `/javascripts/**`, `/stylesheets/**`, `/search/**`, MkDocs theme assets, `/404.html`, `/sitemap.xml`, `/sitemap.xml.gz` | MkDocs owns existing files; assembly extends the sitemap with Astro routes once and validates search links. Do not move old downloadable fixture URLs. |
| `/site-build.json` | Assembly owner; revision, build input hashes, route inventory and SHA-256 of every delivered file except this receipt itself. |

The only allowed HTML replacement is the exact pair `index.html`, `index.zh-CN/index.html`. `extract_reference_home(site_dir, output_dir)` extracts only the trusted MkDocs `<article>` content, strips MkDocs edit controls and scripts, keeps all content heading IDs, rewrites each relative link against the original route, and validates uniqueness. `web/src/components/LegacyOverview.astro` renders it statically. Scope neutral article styling under `.legacy-overview`; do not import MkDocs navigation or its JS. New Astro headings use `product-` IDs. The old English `#quant-backtest-engine`, `#start-here`, `#names-used-in-these-docs`, `#responsibilities`, `#adoption-status` remain at `/`; the Chinese root retains `#quant-backtest-engine`, `#_1`–`#_4`. Refresh the inventory for newly added headings. These are real rendered anchors, not English-to-Chinese slug guesses.

The two root files are consumed and excluded before union, not overwritten by copy order. All other output-path collisions, including identical duplicate asset bytes, fail the build. Reject symlinks, traversal, files outside the declared roots and unknown output namespaces. Keep direct `.html` forms and percent-encoded fragment links working where the existing output supports them. Preserve old tutorial heading and control IDs; do not redirect an old fragment to a generic new landing. `route-anchor-inventory.json` records observed actual HTML; Task 19 must refresh it from clean retained PR 19 and the current merged target before migrating anything.

## 10.3 Existing scene reuse and bounded controls

Retain PR 19 (`4820af3b82940e7697cb8c92154315b1d59ee23d`) attribution, committed source history, exporters, catalog keys, exact fixture evidence and tests. Keep its branch/worktree until the controller proves integration. Preserve historical owner claims as historical evidence, never relabel old bytes as Engine-generated current results.

| Scene | Exact retained preset IDs | New presentation and evidence boundary |
| --- | --- | --- |
| `flow` | `roundtrip` | Causal stages and actual Rust quote/order/fill/account events; supplied-order fixture does not contain a fitted forecast or optimizer. Unsupported forecast stages are explanatory, with no invented numbers. |
| `book` | `depth` | Book depletion, partial fills, order arrival and report visibility; existing 600 ms presentation delay remains explicitly an illustration, not an execution-owner latency result. |
| `impact` | `small,large,nondecaying,close` | Unaffected price, temporary state, nondecaying state and actual fill offset share one timeline; impact already in price is not charged again. |
| `cost` | `once` | Ledger debit versus descriptive spread/impact/opportunity shortfall; one financial owner. |
| `lots` | `no-minimum,minimum,grid` | Feasible integer grid, heuristic and bounded exact answer. Only this enumerated domain supports an optimum claim. |
| `paths` | `thin,deep,market-up,feedback` | Synchronized independent accounts with forecast/market hashes, declared policy changes and visible pending state. |
| `selection` | `null-search` | All six attempted portfolios remain visible, with the actual Platform analytical/teaching owner; no PBO estimate or out-of-sample claim. |
| `risk` | `recovery,shared,residual,actions,risk-full,risk-missing` | Separate restoration, allocation, residual inventory, capital/rights and analytical calibration evidence; unknown remains unknown. |

These 21 presets are the first fixed grid, not a Cartesian product of free parameters. Exported configuration determines labels. In particular `impact.large` changes quantity to 200 **and spacing to 120 seconds**; `small` uses 100 and 60 seconds, `close` 100 and 10 seconds, `nondecaying` 100 and 60 seconds with coefficient 0.001. Do not describe `large` as changing size alone. All use transient coefficient 0.002 and decay time 60 seconds. The integer domain is `{0,1,2,3}²`, cash 14, prices `(6,4)`, zero or unit minimum fee; targets `(1.6,1.6)` or `(1.5,1.5)` are fixed owner inputs. Path caps are 0.1 and 0.5, while `market-up` changes the last external price to 10.5 and `feedback` changes the declared policy. Show changes explicitly; no fictitious cross-product option is selectable.

Expanded latency, liquidity, impact or initial-guess controls must first acquire a finite, versioned `preset-grid.json` with exact resolved inputs, registered owner call, seed (or explicit deterministic null), expected capabilities and generated artifact hash for every selectable tuple. Missing tuples are disabled and explained. Continuous controls are limited to animation position; no intermediate cash, fills, prices, costs, optimizer states or returns may be invented.

## 10.4 Trace, source and hash contract

Keep `engine-method-replay.v1` and its current input/config/run digest definitions intact. Add `engine-learning-manifest.v1` and `engine-learning-trace.v1`, specified in `docs/assets/learning/schemas/`. The manifest references the exact fixture bytes and one trace per scene/preset; the adjacent `2026-11-09-learning-trace.schema.json` is a concrete design schema starting point. There is no self-referential hash.

The manifest has `schema`, `provider_revisions`, `exporter_sources`, `fixture:{url,sha256}`, `sources:{url,sha256}`, `catalogs:{en:{url,sha256},zh-CN:{url,sha256}}`, `preset_grid:{url,sha256}`, and ordered `traces:[{scene_id,preset_id,url,sha256}]`. Every URL is a base-relative same-site path, never a private path. The SHA is lowercase SHA-256 over raw served UTF-8 bytes. No JSON parse/stringify round trip participates in byte checks. Existing owner input/config hashes retain their documented canonical serialization; a transport byte SHA does not replace them.

Original run bindings are **zero/one/many named calls**, not a single scene digest. `bindings.run_sha256` is a map copied exactly from the selected original scenario's `run_sha256`, preserving every key and digest. `bindings.run_bindings_pointer` points to that original map in the hash-bound fixture. `run_bindings_status` is `available` only for a nonempty map, with `run_bindings_reason_key: null`; an empty original map requires `unavailable` and the nonempty reason key `provenance.named_run_binding_not_recorded`. In this case “unavailable” refers only to named run-digest evidence: original result/source/input/config/fixture evidence remains usable. Missing `run_sha256` in an unexpected input schema fails validation; it is not silently converted to the known empty-map case. Do not pick one call, rename a call, drop a contributor, or hash the map into a replacement scalar.

`bindings.calls` has exactly the same keys as `bindings.run_sha256`. Each entry is `{input_pointer,digest_pointer,owner_id,source_ids}`: its pointers resolve to the original `inputs/runs/<name>` definition and `run_sha256/<name>` digest, respectively; its source IDs identify the real pinned exporter/provider call path. JSON Pointer tokens use RFC 6901 escaping, and scenario array indices are resolved from the selected stable ID, not hardcoded globally. Preserve the original digest algorithm: `method_fixture_common.scenario` hashes each serialized **call definition**, not the resulting financial output. The existing complete input/config digests also remain unchanged. The top-level `provider` is a primary display/dispatch identity, never a substitute for the per-call actual owner and source list. A scene may combine multiple distinct calls; each financial run still has exactly one financial owner.

Event `source_pointers` maps every `values` key to a `ValueSource` record `{source_pointer,run_names,run_binding_status,reason_key}`. `source_pointer` resolves to the exact original displayed value, not an inferred result; `run_names` lists all and only contributing named calls proven by the pinned exporter call path and whose definitions/digests are bound above. Multiple contributors are permitted. `available` requires one or more names and null reason. `unavailable` requires no names and a nonempty reason describing missing named-run evidence; `not_applicable` requires no names and a reason for genuinely static metadata/input rather than a financial result. Neither status is permission to omit a known contributor. The validator checks the exporter-to-value correspondence, not merely that a listed key exists.

Each table retains its original `source_pointer` plus `run_names`, `run_binding_status`, `reason_key` for the whole table, and `value_sources` keyed by projected-cell JSON Pointer, for example `/rows/0/cash`, with one `ValueSource` for every displayed cell. The table's names must equal the union of its cell contributors; mixed static cells retain their own `not_applicable` reasons. Original table pointers and cell pointers must resolve into the same declared fixture, and per-cell values must match their source under the documented serialization projection. Do not use a table-wide union to hide a missing or incorrectly assigned cell contributor. Every original call remains in `bindings`, even if its result is not displayed by one particular view. Additional original numeric ns/index fields are converted to strings before any JavaScript-number parsing, using exact arbitrary-precision integer-to-base-10 conversion; preserve original `units`, explicit currency/unknown currency, clock kind/timezone, shares, return fractions, squared basis points and dimensionless ratios. Semantic checks reject incompatible labels, scaling and clock conversions; this adds no economic calculation.

Concrete required cases: `flow.roundtrip` keeps `{}` and an empty `calls` map with the explicit missing-named-binding reason while retaining its actual Rust result; `book.depth` keeps exactly `matcher`; each `lots` preset keeps `planning` and all 16 `grid-i-j` entries. Planning-state cells point to `planning`, grid cells to the actual relevant grid call(s), with constants separately identified. `risk.shared` keeps `allocation,execution,netting`; `risk.residual` keeps `session,wealth`; `risk.actions` keeps `baseline,continuation`. The exporter audit must map each result/cell to its actual producers, including transitive contributors where a composed result consumes their output. It must not attach every call indiscriminately or erase the preceding execution because a final analytics/allocation call also exists.

An optional `bindings.projection_ref:{url,sha256}` may identify a **separate** safe-client projection artifact. Its SHA-256 covers that artifact's exact served UTF-8 bytes; the referenced projection excludes this digest/reference and is not the trace file itself. This byte contract is distinct from every named owner-call digest. It may be omitted, never synthesized to fill a missing original run binding. The manifest's trace SHA remains the byte hash of the complete trace, without self-reference. No aggregate run digest is introduced by this amendment.

Each trace identifies scene/preset, primary provider/backend/version, original named-run/input/config/forecast/market hashes where applicable, generated-source and dependency identities, input seed, policy mode, capability/evidence status and explicit source references. It carries exact ordered `events`, separate `tables` for all original ledgers/grid/attempts and an optional `comparison` map. Each event includes stable `event_id`, contiguous `ordinal`, `clock:{kind,value,timezone}`, `stage`, actual prior-event `depends_on`, and `values`. Clock kinds are `utc_ns`, `elapsed_ms`, `elapsed_s`, `session_date`, `iso_datetime`, `event_index`, `trial_index`; values are strings, with UTC explicitly selected for absolute timestamps. Never equate event index or session date to a UTC nanosecond. Same-clock rows retain owner ordering and ordinal. Financial values are decimal strings or null; booleans remain booleans. No NaN/Infinity or unsafe JSON numeric clocks. Missing/unsupported evidence gets a status/reason, not a fabricated zero.

`project_method_trace(fixture, scene_id, preset_id)` is a build/export projection, not an economic model: every displayed value points to its original JSON Pointer; it may reshape but must not compute fills, balances, cost, risk or optimization. Extra causal stages/solver iterates require an owner-produced trace, not inference from a final result. `validate_learning_assets(manifest_path)` checks schemas, original zero/one/many run maps and absence reasons, complete per-call identities, per-value/per-table contributor pointers and unions, all references, preset coverage, units/currency and exact clock serialization/order/dependencies, source-pointer/value equality, allowed public links, provider identity and all file digests. Unknown schema versions or mismatched hashes fail the build. Hydration validates the small projected payload; mismatch disables replay while preserving static tables and displays a localized error. Build tests prove the embedded projection and downloaded artifact refer to the same manifest and values.

Source records distinguish `academic_background`, `documented_discussion`, `project_interpretation`, `implemented_model`, `synthetic_execution_evidence`, `real_market_calibration`. Each record has `id,class,title,url,locator,claim,limitations,availability`, plus pinned revision/hash for executable evidence. A discussion motivates a hypothesis; an academic tutorial explains a method; neither proves an implemented finance model or calibrated execution response. A phase-retrieval example must not be cited as finance-model validation. Private discussions are described only as public-safe project interpretation unless an actual publishable source is available. No private chat quotes, account/order data, host paths or personal source locations are published.

Every scene visibly states source classes, `calibration: unavailable|synthetic_only|empirical`, sample scope, model assumptions, real owner and unsupported capability. This task has no empirical calibration artifact, so `empirical` must fail validation unless separately accompanied by verified sample/method/coverage evidence. Multiple prepared paths are a sensitivity set, not independent market observations or a probability distribution; show sample counts and do not label a histogram a market probability.

Capability boundary: the implemented transient-impact planner and its declared convex-QP domain, finite discrete search and heuristic/best-found reports retain their actual solver limits. A synthetic nondecaying term in `impact.nondecaying` is an executed sensitivity assumption, not a completed calibrated permanent-impact mechanism; no calibrated permanent or cross-asset impact is established. Conceptual cross-impact diagrams must be labeled conceptual and have no invented executable trace. The topic list is not a capability completion checklist.

## 10.5 React state and synchronized interaction contract

Use one `ReplayWorkbench` island per lab, containing controls, causal diagram, event timeline, ledger, charts and scenario comparison. No separately hydrated widgets maintain competing financial/event cursors. Props are validated `LearningTrace[]`, catalog, locale and manifest identity; state is `{presetId,eventOrdinal,playing,speed,comparisonPresetIds,reducedMotion}`. Speed is presentation-only `0.5|1|2`; the default is 1 and autoplay is off. `reduceReplay(state, action, traceIndex)` accepts only `SELECT_PRESET, SELECT_EVENT, NEXT, PREVIOUS, RESET, PLAY, PAUSE, SET_SPEED, SET_COMPARISON, SET_REDUCED_MOTION`.

NEXT/PREVIOUS clamp at bounds; RESET selects event 0 and pauses; changing preset/comparison pauses and resets to the first valid comparison point. PLAY at the final event is a no-op until reset. Explicit steps and seeks pause playback. A timer advances exact events only, is cancelled on unmount/visibility change, and pauses on hidden tabs. Returning to the tab never resumes automatically. Decimal text changes only at an event boundary. A 0–1 visual progress may animate geometry between recorded events, but financial text and plots never portray new economic states. Reduced-motion mode disables interpolation and timed autoplay; Play is disabled with an explanation, while step/previous/reset and selection stay usable.

Comparisons use exporter-defined `comparison:{axis,points:[{id,label_key,events:{preset_id:event_id|null}}]}`. At a synchronized point, each scenario reads its own account/event; null means no corresponding event. Do not zip unequal histories, forward-fill unknown economic evidence or overlay incompatible clock bases. For the retained paths, use matched decision/fill stages and verify actual clock compatibility; no distribution or random seed is inferred from four cases. Selection and restore indices use their own labeled axes.

The finite optimizer grid already supports a nonconvex/discrete feasibility lesson. A continuous nonconvex animation additionally requires actual solver callbacks exposing start, iterate, objective, constraint residual, termination reason and best found feasible candidate, under a fixed registered multistart grid. Each start uses the same declared objective and constraints. The browser may draw a recorded trajectory but cannot calculate an objective surface or solve a portfolio. General research optimizers remain Platform-owned and are optional exporter dependencies; Engine owns its bounded execution planners. If the real solver has no iterate API, show the real start/final results and say intermediate trajectory is unavailable. Never manufacture a descent path or claim global optimality. A future multi-start trace is a separately versioned evidence addition, not grounds to block the already-authorized financial migration or silently mark an unimplemented animation complete.

## 10.6 Locale, accessibility and narrative

English is the default at unsuffixed Astro routes. Chinese paths are explicit and linked reciprocally. `docs/assets/method/en.json` and `zh-CN.json` remain the authoritative shared semantic catalogs for preserved scene terms, extended with `learning.*`, `source.*`, `evidence.*` and control keys. New explanatory Markdown lives in `web/src/content/learn/{en,zh-CN}/`. Machine IDs, source hashes and stored financial values never change with language. Missing Chinese messages fall back to English and are reported in tests. Display dates with explicit clock semantics/timezone and preserve exact downloadable decimal/nanosecond strings beside any human formatting.

`engine.site.locale.v1` stores only `en` or `zh-CN`; storage failures are nonfatal. The URL remains authoritative: no automatic redirect of a deep link or hash. A saved choice determines subsequent generated navigation targets and the visible “continue in Chinese/English” link on the English root; explicit switch writes preference and navigates the paired URL/scene anchor. No browser-language autodetection overrides English default. Legacy MkDocs gets the same small framework-free preference helper and reciprocal route map; React remains the only client component framework. Navigation across MkDocs/Astro uses ordinary document links, avoiding competing SPA lifecycle owners.

All narratives, provenance, all 21 presets' result rows, complete finite grids and every attempted trial are in SSR/static HTML, not hidden until hydration. Controls become enabled only after successful hydration. Native buttons/selects and range controls have labels, visible focus, keyboard operation and current-event announcements; arrow stepping is scoped to a focused timeline, never steals text/select keys. Respect `prefers-reduced-motion`; provide accessible table alternatives to every chart. Test 320px and desktop, light/dark, JS disabled, blocked storage, hydration error, navigation away/back and changing locale mid-scene. Expanding a static `<details>` table must work without JS.

## 10.7 Build, deployment and acceptance

Keep `.github/workflows/docs.yml` as the sole Pages deployment owner. Build MkDocs to `TASK_DATA/site-mkdocs`, extract roots and validate artifacts, build Astro to `TASK_DATA/site-astro`, then `assemble_site(mkdocs_dir,astro_dir,learning_dir,route_manifest,output_dir)` creates a fresh `TASK_DATA/site-assembled`. Never use an existing production directory as staging. Assembly writes `site-build.json`, one sitemap including both route sets, and verifies all local links/fragments/assets under the base. Existing MkDocs search remains technical-reference search and says so; learning navigation covers all eight scenes without claiming a unified search index.

PR builds run the complete assembly and acceptance checks but do not deploy. Main builds upload exactly the assembled artifact once and the existing deploy job publishes it once. No Astro-specific second deploy workflow, alternate Pages branch or always-on server. CI output directories use `RUNNER_TEMP`; local outputs and browser profile/cache live under the Engine task data contract. Preserve locked MkDocs validation and all provider/economic checks; Astro does not replace them. Pin actions and frontend dependencies; record audit results and treat unexplained high/critical production dependency findings as a gate.

Acceptance requires clean current merged Engine owner regeneration, retained optional analytical owner identity, byte/source/schema/typed-call mutation checks, all-eight-scene fixtures, all legacy routes and anchors, fixed-grid controls and synchronization tests, real built-site browser tests and no-JS exact-table checks. Preserve original DOM/replay tests for retained MkDocs functionality; add React reducer/component tests and actual Playwright checks of the assembled site. Task 20 verifies the deployed build receipt, HTML and fixture/download hashes against the merged revision, including homepage fragment links, locale persistence and both rendering owners. A successful job or screenshot alone is insufficient. Close PR 19 only after exact incorporation evidence; clean its resources only after the controller confirms no unique work remains.

Implementation detail: homepage fragments are generated on every build from the current source/rendered article and remain outside the repository; never commit a frozen HTML archive. MkDocs is the sole staging producer of `docs/assets/learning/**`; assembly validates that output against the original `learning_dir` input and copies it once. Astro consumes the data but must not emit another `public/assets/learning` copy. Both renderer inputs and root extraction must share the same clean source revision and expected manifest/lock hashes; a worker-directory name is not source identity. All shared assets participate in the same collision checks.

## 11. Acceptance that proves reuse

Required clean-room examples use installed artifacts outside all repository roots:

1. Standard-library SDK + recorded Rust executable, no Platform/Runtime/Research: existing USD 10,000 example ends at 10,019.78 with 0.22 fees.
2. Installed optional Python core, no Platform/Runtime/Research/Torch: CNY session with partial fills, fees, locks, rights, capital flow, unknown marks and every-event restore.
3. Optional planning/scenario profile: actual independent accounts, bounded planner/oracle checks, execution versus market-path semantics and explicit consumer callbacks.
4. Platform consumer and a separate minimal caller use the same published Engine interfaces and agree with hand expectations on supported aligned inputs.
5. Runtime's additive Engine-provider path survives real termination at durability/admission boundaries with complete uninterrupted/restored financial parity.

Audit installed distribution/module ownership and imports; moving imports behind lazy functions alone does not prove removal of an execution-time Platform dependency. No source-tree PYTHONPATH or editable-worktree import may masquerade as an installed-wheel test.

Preserve independent hand ledgers, one-nanosecond causal boundaries, source/tape mutation rejection, unsuccessful attempts, input/config digest sensitivity, actual-vs-visible state and constrained exits. Compare all economic tables exactly where extraction preserves calculations. Any allowed identity/version difference is explicitly enumerated and reviewed; do not broadly drop columns or widen tolerances to obtain parity.

Cross-backend equality is asserted only for aligned fee/clock/lot/liquidity/valuation/rule domains. Backend-specific behavior and unsupported cases remain observable. Existing period-return comparison is not a full financial oracle.

Record exact source/provider/consumer/dependency/executable identities, commands, exit codes and skips. Updated documentation/link/browser checks are required, not a substitute for economic tests. Preserve source attribution/license notices of moved files and verify the produced package/source contents.

## 12. Non-goals and review decisions

No new tick acquisition, broker connection/orders, production configuration/scheduler changes, real cost/impact calibration, historical auction queues, real borrow/margin approval or prospective alpha evidence is authorized here. An architecture transfer does not turn synthetic tests into real-market evidence.

Concrete defaults proposed for review:
- Separate dependency-free SDK and distinct optional Engine-owned Python core namespace.
- Keep general factor/risk/statistical research in Platform; extract backtest-specific mechanisms.
- Explicit backend selection and versioned additive contracts; no automatic fallback or checkpoint rebinding.
- Migrate the financial dependency cluster as a unit; mechanisms may move first when independently closed.
- Code, executable examples and corresponding EN/ZH docs co-migrate; preserve historical evidence and compatibility links.
- Keep Runtime operational ownership and private research/trial authority outside Engine.

After owner approval, write a task-level implementation plan with precise files, contracts, tests, provider/consumer order and per-wave review gates. This design is not that implementation plan and does not claim that any transfer, new package or API already exists.
