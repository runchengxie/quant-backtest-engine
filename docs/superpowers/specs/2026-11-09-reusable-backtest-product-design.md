# Reusable backtesting product: architecture and staged ownership transfer

Status: proposed design for owner review, 2026-11-09. The owner selected the direction: Engine becomes the independently reusable backtesting product, with an optional Python implementation and the existing Rust execution backend. This document makes the interfaces, migration boundaries and acceptance gates concrete. No implementation migration is authorized by this document's publication.

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
| M4 Planning and scenarios | Transfer bounded execution-aware planners/allocation/finite exits; compose independent scenario runs and external policy callbacks | Prefunding/capacity/feedback correctness; dependency closure without research/factor/training leakage; failure retention |
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

For M5, daily execution_sim reporting currently imports research metrics, position replay mixes holding selection and simulation, and execution calendars can fetch provider data. Introduce execution summary DTOs, explicit targets and supplied calendar artifacts before moving that financial implementation. Keep factor IC analysis, top-k selection and provider authentication with their actual external owners.

| Current Platform documentation | Canonical Engine destination after the corresponding wave |
| --- | --- |
| backtest/market-paths.md and .zh-CN.md | Same backtest/market-paths pair with M2 scenario mechanism |
| backtest/minute-session.md and .zh-CN.md; guides/minute-execution.en.md and its Chinese original | Engine backtest/minute-session pair and guides/minute-execution pair with M3 |
| backtest/transaction-cost-evidence pair; analytics cost-scope explanations | Engine cost/evidence guide with M2/M4; explicit statistical limitations retained |
| concepts/impact-planning and discrete-inventory EN/ZH pairs | Engine same-topic optional-planner guides with M4 |
| backtest/sleeve-allocation pair; execution-integrity/paper-account/account-feedback/capital/reconciliation guides | Engine execution allocation/account/evidence guides with M3/M4; add missing Chinese product companions |
| contracts/pending-allocation; signed/sparse optimization guides | Split execution reservation contract into Engine; generic optimization documentation stays Platform |
| execution-simulation/sequenced-execution/corporate-action/dated-fee/backtest-output guides | Engine mechanism/result guides after M5; Platform retains target-construction and analysis workflows |
| backtest/risk-calibration pair and factor-risk/model guides | Remain Platform; Engine links to the separate public analytical owner |
| Platform install/API/entry-point/overview and ownership maps | Remain Platform, updated as consumer documentation and compatibility pointers |
| Runtime financial-sessions/session-stream/queued-sessions/ownership guides | Remain Runtime, updated with the actual new provider and unchanged durable job responsibilities |

Preserve existing .en, .en-US, unqualified Chinese and .zh-CN old routes through an explicit locale-aware map. Do not assume all unqualified existing pages are English. Add current tested combinations beside historical matrices; do not replace old tested revisions or equate main with an alpha release.

PR 19's exporter currently imports allowlisted quant_platform types and binds those class/module source hashes. Update the typed-call allowlist, owner revisions/URLs and every executed exporter/helper/source hash with each transfer, then regenerate from clean merged providers. Retain previous fixture provenance as historical evidence. Its required Runtime checkout only hashes a documentation file; replace that build dependency with an optional versioned documentation reference. A retained risk/null teaching scene may still use Platform as a separate optional analytical owner, without making Platform a runtime dependency of Engine.

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
