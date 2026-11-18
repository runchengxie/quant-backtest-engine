# Execution fidelity and mechanism presentation implementation plan

> For agentic workers: use superpowers:executing-plans, inline execution.

**Goal:** Make execution evidence and remaining production gates inspectable; present mechanisms with the standards site's restrained document and diagram vocabulary.

**Architecture:** Preserve the financial owners and pinned native wire contracts. Add an explicit full-depth snapshot reconstruction diagnostic alongside the historical best-quote diagnostic. Validate same-price FIFO, arrival timing and cancellation races against hand oracles; keep any external comparator isolated. Group the website by mechanisms, with implementation boundaries and reference links adjacent to demonstrations.

**Spec:** User-approved continuation of L2 reconstruction, execution assumptions and independent HftBacktest evaluation; website reference is quant-workspace-standards at e63f5d7. No claim of live execution calibration or production approval.

## Constraints

- Synthetic fixtures only in source; generated evidence outside source.
- Preserve existing replay behavior and request/result schemas.
- No silent fallback, second cash ledger, or union-of-backends capability claim.
- English default and paired Chinese catalogs/docs; preserve all old lesson URLs.
- Continuous loop, pause, previous/next, reduced-motion and keyboard behavior remain supported.
- No new production dependency on Backtrader or HftBacktest in this batch.

## Tasks

- [x] Add a strict, explicitly scoped depth-reconstruction API with tests for initial depth, deeper-level mismatches, unknown cancellation, out-of-order input, and ambiguous snapshot boundaries. Missing evidence must remain unavailable.
- [x] Add hand-oracle execution fidelity checks for queue priority and arrival/cancel races. Inspect pinned Nautilus queue/latency APIs and record adapter-specific gaps. Evaluate an external comparator in an isolated environment if its locked distribution is obtainable.
- [x] Add paired execution acceptance and framework comparison documentation, with production gates and exact test commands.
- [x] Replace eight equally weighted homepage experiments with mechanism groups; retain shared account and advanced diagnostics below. Use localized formal titles and nearby scope statements.
- [x] Align page and diagram typography, strokes, markers and colors with the standards site. Preserve numerical/source identity and all interaction contracts.
- [ ] Run affected core tests, native required checks, strict site build, browser verification and prose review; deliver through PR and verified Pages publication.
