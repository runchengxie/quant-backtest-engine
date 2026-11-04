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

- [x] Add failing iterator API parity, source-error, late-invalid and consumption tests.
- [x] Introduce SessionConfig and persistent validation, preserving request checks.
- [x] Move pending/rules into shared state and load one session at a time.
- [x] Share replay driver between existing and iterator APIs; verify economic parity.

## Task 2

- [x] Document API, retention limits and error semantics in English and Chinese.
- [x] Run fmt, clippy, all Rust tests, synthetic CLI, docs and Python gates.
- [x] Commit implementation with exact validation and limitations for parent review.

## Validation record

The implementation passed 56 Rust tests, including 24 session tests, with complete
result parity between the owned iterator and v2 entry point. Existing economic
assertions remain independent checks. Invalid-input tests observe source reads
through atomic counters and assert the expected error category.

`cargo fmt --all --check`, locked clippy with warnings denied, locked tests,
roundtrip and session synthetic CLI requests, the target-weight tutorial, strict
MkDocs build and rendered locale/link validation passed. Python checks passed
11 SDK tests against the built engine and 12 project-tool tests. Rustc was 1.99.1;
Nautilus dependencies remained locked at 0.66.0.

A separate synthetic harness generated 100 sessions with 1,000 quotes each for one
instrument and no orders, totaling 100,000 quotes. Both cases linked the same newly
built implementation. Each case used a fresh fork-and-exec child. The eager case
generated and collected sessions in that child's caller thread before calling
`run_sessions`; the iterator case generated each session in the engine worker.
Producer buffers were included in the measured child process. Complete results
were byte-identical. Linux `wait4` `ru_maxrss`, expressed in KiB, measured peak RSS of
88,968 KiB for the full-request path and 30,504 KiB for the lazy iterator path.
These are single-run synthetic measurements, including source buffers and upstream
state. They establish neither a general memory bound nor a speedup.

Parent review identified panic-based source guards that could hide extra reads
behind the worker panic error. The tests now use observable counters and specific
validation errors; the complete suite and clippy passed again.
