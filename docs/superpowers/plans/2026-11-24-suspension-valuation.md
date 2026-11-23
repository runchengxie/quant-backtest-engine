# Suspension Valuation Implementation Plan

Use inline TDD execution and a fresh whole-branch review. Spec: docs/superpowers/specs/2026-11-24-suspension-valuation-design.md.

- [ ] Add failing synthetic tests for default equivalence, explicit suspension carry/resumption/no fill, missing/unknown/overage/future-only mark rejection, raw/action/ideal/capacity rejection and historical manifest acceptance.
- [ ] Implement optional config fields, suspension evidence projection, policy-aware owner endpoint evidence and SDK/backend compatibility. Preserve one ledger and actual executable quotes.
- [ ] Add direct/backend round-trip parity and source/age evidence tests; run affected and full Core/SDK tests and required repository gates without changing hooks.
- [ ] Update linked EN/ZH product docs. Commit; root coordinator handles provider PR/merge before consumers.

Review focus: unknown suspension metadata, prior quotes that the ledger never held, global-session age boundaries, unsupported raw/action modes, old immutable manifest shapes and current-vs-policy marks.
