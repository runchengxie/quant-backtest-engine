# Daily symbol attribution implementation plan

**Goal:** Expose attribution captured from the existing daily financial owner without changing execution arithmetic.

**Architecture:** Snapshot owner position values after each session, combine with that session's recorded fill principal and fees, and reconcile to the existing equity change. Append optional result tables; never reconstruct holdings or cash.

**Tech stack:** Python, pandas, pytest.

## Constraints and review focus

Synthetic fixtures only. Existing result constructors remain compatible. Corporate actions are unsupported, and incomplete opening or closing valuation withholds PnL. Include exited symbols and fee-only rows. Preserve existing daily/orders/fills outputs. Cash-only sessions must reconcile without invented symbol exposure.

## Tasks

- [x] Add failing synthetic tests for entry fees, price changes, exits, policy marks, incomplete endpoints and unsupported corporate actions.
- [x] Add endpoint attribution capture beside the existing owner loop and optional result tables; test reconciliation and unchanged legacy tables.
- [x] Document exact columns, status, units and supported semantics in linked English/Chinese documentation.
- [x] Run owner Python regressions, static checks, Rust gates, synthetic CLI, ownership and strict documentation gates; record actual outcomes and commit locally.

Execution is native in this isolated task worktree under the explicitly assigned implementation task.

## Validation

Owner endpoint tests and the complete daily regression suite pass. Exact NaN-aware comparison against the base revision preserves all seven legacy fields across normal execution, approved carried marks, incomplete marks and corporate actions. Rust formatting, lint, tests and the documented synthetic CLI pass; ownership and paired rendered documentation gates pass. No code ownership transfer occurred, so the migration registry remains unchanged. Detailed generated receipts stay outside source.
