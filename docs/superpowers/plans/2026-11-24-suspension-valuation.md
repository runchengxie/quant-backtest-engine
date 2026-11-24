# Suspension Valuation Implementation Plan

Use inline TDD execution and a fresh whole-branch review. Spec: docs/superpowers/specs/2026-11-24-suspension-valuation-design.md.

- [x] Add failing synthetic tests for default equivalence, explicit suspension carry/resumption/no fill, missing/unknown/overage/future-only mark rejection, raw/action/ideal/capacity rejection and historical manifest acceptance.
- [x] Implement optional config fields, suspension evidence projection, policy-aware owner endpoint evidence and SDK/backend compatibility. Preserve one ledger and actual executable quotes.
- [x] Add direct/backend round-trip parity and source/age evidence tests; run affected and full Core/SDK tests and required repository gates without changing hooks.
- [x] Update linked EN/ZH product docs. Commit; root coordinator handles provider PR/merge before consumers.

Review focus: unknown suspension metadata, prior quotes that the ledger never held, global-session age boundaries, unsupported raw/action modes, old immutable manifest shapes and current-vs-policy marks.


Implementation evidence: synthetic policy and prepared-selector regressions were observed RED before their fixes; action-artifact admission was separately observed RED→GREEN. The existing ledger and executable quote table remain unchanged. Homogeneous parallel tuple metadata passed both all-empty and mixed-row Parquet round trips. Ordinary wheels are used for isolated `python -I` full-suite validation; the initial source-PYTHONPATH preflight could not satisfy isolated packaging imports. Final source, gate logs and wheel receipts are retained outside Git. Fresh whole-branch review and publication remain the root coordinator's responsibility.


Final review fix pass: 20 material regressions failed before fixes, covering execution-selector aliases and prepared-table provenance, order-dependent normalized quote duplicates, and missing applied-policy context in normalized summaries. Centralized selector validation and bound projection metadata close native/direct/prepared bypasses; opt-in preparation rejects all duplicate normalized daily keys; native and normalized summaries retain the applied policy and carried-endpoint count. Additional acceptance covers identical duplicates, missing/conflicting projection metadata and default duplicate compatibility. Earlier validation at eaab873 predates these fixes; final installed-wheel and affected gates are recorded separately outside Git. No second review was dispatched.

The fix pass also observed a RED regression proving duplicate-key normalization must not create executable dates from timestamp labels. Normalization is now confined to validation keys; original executable-date parsing remains unchanged.
