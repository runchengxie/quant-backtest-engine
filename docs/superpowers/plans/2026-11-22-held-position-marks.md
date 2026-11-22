# Held-position mark evidence implementation plan

Design: [held-position endpoint marks](../specs/2026-11-22-held-position-marks.md).
The user authorized implementation; root owns provider publication and consumers.

1. Write failing synthetic daily-runner and owner tests for future/unheld targets,
   missing held current marks, stale NAV, recovery intervals, exits/cash and rights.
2. Add a pure endpoint-evidence helper and optional result field. Instrument the
   existing ideal/adjusted live ledgers after valuation. Consume the emitted
   evidence in runner; preserve arithmetic and all financial tables.
3. Preserve the additive table in raw product transport. Add compatibility and
   transport checks. Update linked EN/ZH input contracts and ownership record.
4. Run focused then complete Core/SDK tests, Ruff/type checks where required,
   ownership checks, Cargo fmt/Clippy/tests/synthetic example and external strict
   docs build/verification. Record exact commands and any limitations.
5. Commit only this task after validation. Root independently reviews and controls
   push, merge and provider-before-consumer integration.
