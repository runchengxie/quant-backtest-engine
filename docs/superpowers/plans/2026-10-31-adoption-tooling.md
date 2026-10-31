# Engine adoption tooling implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the adoption changes; benchmark work is independently delegated.

**Goal:** Make the experimental engine easy to try and assess with executable examples, correctness evidence, compatibility records and downloadable releases.

**Architecture:** Keep NautilusTrader as the execution/accounting owner. Python standard-library tools drive the existing CLI without implementing another simulator. Consumer adapters remain opt-in.

**Tech Stack:** Rust 1.99.0, NautilusTrader 0.66.0, Python 3.13, MkDocs Material, GitHub Actions.

**Spec:** User-authorized six adoption priorities in the conversation, continuing the independent-engine and portfolio-migration designs.

## Global constraints

- Synthetic fixtures only; generated outputs are external to source trees.
- Decimal monetary values; no fabricated corporate-action or execution-aware parity.
- Default English documentation with matching Chinese pages.
- Provider merges before consumers; test actual binary/consumer revision pairs.
- Linux x86_64 is the first distribution target; other platforms require separate evidence.

## Review focus

- Future information must not enter sizing or fill eligibility.
- Projected sale cash is not evidence of a completed sale.
- Tutorial results must reconcile actual upstream fills, not reference marks alone.
- Benchmark failures and nondeterministic output must fail explicitly.
- Distributed binaries must accompany exact source, dependency licenses and rebuild instructions.

## Tasks

- [ ] Finish runtime v6 and platform adapter integration, required checks and independent review, separate PRs.
- [ ] Add `project_tools/tutorial.py`: generate orders via `size`, execute sessions, assert hand-computable daily balances and refusals. Test via real binary in CI. Add bilingual tutorial pages.
- [ ] Add bilingual capability/correctness matrices with test links, current exclusions and compatibility records. Add clear version/state entries to home and quickstart.
- [ ] Add reproducible benchmark tool and bilingual measured report. Record warmup, per-process RSS, latency and total throughput separately; no unsupported language comparison.
- [ ] Add Linux release packaging with checksums, source/dependency bundle and toolchain record; test archive and clean offline rebuild. Publish experimental prerelease only after merged checks pass.
- [ ] Verify strict docs and locale links, full Rust gates, example, benchmark error path and release package; review changes, PR/merge and clean only task resources.
