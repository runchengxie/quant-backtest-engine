# Incremental session input implementation plan

Goal: offer owned whole-session library input with identical economic outputs.
Architecture: shared Nautilus 0.66 driver on one dedicated thread, incremental
validation and replaceable current-session strategy input.
Spec: ../specs/2026-11-05-incremental-session-input-design.md

## Constraints and review focus

Preserve v2 schemas, profiled APIs, timestamp ties and order priority. Keep generated
outputs outside Git. Check late failures, empty input, worker isolation, source
pull timing and stale strategy state. Retain full final reports explicitly.

## Task 1

- [ ] Add failing iterator API parity, source-error, late-invalid and consumption tests.
- [ ] Introduce SessionConfig and persistent validation, preserving request checks.
- [ ] Move pending/rules into shared state and load one session at a time.
- [ ] Share replay driver between existing and iterator APIs; verify economic parity.

## Task 2

- [ ] Document API, retention limits and error semantics in English and Chinese.
- [ ] Run fmt, clippy, all Rust tests, synthetic CLI, docs and Python gates.
- [ ] Commit implementation with exact validation and limitations for parent review.
