# Owner control study implementation plan

[简体中文](2026-11-25-owner-control.zh-CN.md)

**Goal:** Connect fixed execution controls to one financial owner and test stress/recovery.
**Architecture:** Synthetic fixtures and policy bridge into existing MinuteSession;
post-run metrics consume owner tables only. External artifacts bind source/inputs.
**Spec:** `docs/superpowers/specs/2026-11-25-owner-control-design.md`.

- [ ] Test-first `planning/owner_control.py` and `planning/owner_control_case.py`:
  `OwnerControlCase` immutable validated config, `build_session(case)`,
  `restore_case(case, checkpoint)`, `run_case(case)` returning owner result and
  session/policy diagnostics. Public owner owns all financial state.
- [ ] Observe RED then implement `OwnerLiquidationPolicy` with four modes, causal
  delivered-state/pending gates, fixed no-retry schedules, LQ proxy and integer
  target encoding. Versioned JSON checkpoint binds configuration/helper versions.
- [ ] Test-first `planning/owner_control_audit.py`: `audit_case(case, result, trace)`
  validates quantities/fees/cash and conditional completion; hand zero-impact and
  commission cases establish no double cost. No replacement financial ledger.
- [ ] Test-first checkpoint/recovery and future-bar invariance acceptance using the
  four representative delayed/outage policies. Reject changed case/dependency.
- [ ] Add `scripts/verify/export_owner_control.py`: frozen104panel/96uniquecase
  inventory, all owner traces/tables, hashes and explicit failed/partial statuses;
  retain optional whole-boundary recovery evidence externally. No parameter choice.
- [ ] Independent review of policy/financial boundaries and exported arithmetic.
  Run relevant+full locked Core/SDK, Rust required checks/CLI, ownership, static
  and strict paired docs. Freeze sources during source-bound tests.
- [ ] Commit, push PR to owner's main, inspect exact required checks/current base,
  merge then clean only this task's branch/worktree; preserve external evidence.

File ownership: root owns audit/exporter, experiment/docs/results and Git. A bounded
implementer may own controller/case modules and their tests; no overlapping edits
or Git operations. A fresh independent reviewer owns no source files.
