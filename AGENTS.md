# quant-backtest-engine contributor rules

This public repository owns the versioned engine request/result contract, Rust library,
CLI, thin adapters to upstream backtest engines, and the approved optional Python
financial product as staged in docs/migration/reusable-product.md. M0 records future
ownership; it does not claim the Python core is implemented. It does not own strategy
research, model training, task scheduling, job databases, or production datasets.

- Use synthetic fixtures only. Keep data, results, and build outputs outside the repository.
- Keep engine calls usable without quant-platform or quant-backtest-runtime.
- Each run has one financial owner. Rust reuses upstream execution/accounting; the
  optional extracted Python backend owns its own financial state. Never add a second
  cash ledger to disguise unsupported upstream behavior or silently fall back.
- Completed Engine runtime imports must not depend on Platform, Runtime or private
  research. Keep SDK quant_backtest_engine separate from optional quant_backtest_core.
- Transfer code, executable acceptance and paired EN/ZH docs together; provider
  merges precede consumers. Preserve arithmetic, source/checkpoint identities and
  historical evidence; old checkpoints retain their full pinned legacy environment.
- Keep aliases for two minor releases AND until all supported consumers migrate.
  Update docs/migration/reusable-ownership.json with each transfer.
- Keep factor/risk estimation, training and research publication outside Engine;
  Runtime retains durable job admission and supervision.
- Declare supported capabilities explicitly and reject unsupported semantics.
- Preserve decimal monetary values and explicit UTC nanosecond timestamps in contracts.
- Use task branches and isolated worktrees; deliver via PRs to this repository's main.
- Validate with cargo fmt --all --check, cargo clippy --locked --all-targets -- -D warnings,
  cargo test --locked, the documented synthetic CLI example, and git diff --check.
- Validate ownership with python -m unittest project_tools.test_reusable_ownership -v
  and python project_tools/check_reusable_ownership.py; build strict docs with the
  locked docs environment and run project_tools/check_docs.py on the external site.
- Default documentation is English; provide linked Chinese counterparts.
- Preserve upstream license notices and record the pinned upstream version.
