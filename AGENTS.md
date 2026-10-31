# quant-backtest-engine contributor rules

This public repository owns the versioned engine request/result contract, Rust library,
CLI, and thin adapters to upstream backtest engines. It does not own strategy research,
model training, task scheduling, job databases, or production datasets.

- Use synthetic fixtures only. Keep data, results, and build outputs outside the repository.
- Keep engine calls usable without quant-platform or quant-backtest-runtime.
- Reuse upstream execution and accounting; do not silently introduce a second simulator.
- Declare supported capabilities explicitly and reject unsupported semantics.
- Preserve decimal monetary values and explicit UTC nanosecond timestamps in contracts.
- Use task branches and isolated worktrees; deliver via PRs to this repository's main.
- Validate with cargo fmt --all --check, cargo clippy --locked --all-targets -- -D warnings,
  cargo test --locked, the documented synthetic CLI example, and git diff --check.
- Default documentation is English; provide a linked Chinese introduction.
- Preserve upstream license notices and record the pinned upstream version.
