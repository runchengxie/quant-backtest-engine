# Runtime integration

The engine is independently callable. For durable batch jobs use
[quant-backtest-runtime v5](https://github.com/runchengxie/quant-backtest-runtime/blob/main/docs/development.md#independent-rust-engine-jobs-v5).

1. Build a reviewed, merged engine revision into a stable release directory.
2. Save `engine_request.v1` JSON as a SHA-256-addressed input artifact.
3. Submit a v5 `nautilus.quote_market_orders` job, pinning the executable SHA-256.
4. Configure the executable's absolute path as an operator CLI argument.
5. Read the verified `quant.engine_job_result.v1` snapshot and inspect order statuses.

The runtime remains the sole task-state writer and result publisher. It executes a
held verified inode, inherits address-space limits into the child, terminates/reaps
it on cancellation and timeout, and uses Linux parent-death SIGKILL on hard recovery.
These controls are not an untrusted-code sandbox. A successful job can contain
rejected orders. v1–v4 jobs and their fingerprints are preserved.

The final snapshot is diagnostic evidence. It must not be described as the platform's
execution-aware daily bundle. Market and information-time limits remain those stated
in [execution assumptions](execution.md).

Runtime CI pins engine revision `a2dc923b01c46389f090db7865175c5d87b6819c` and runs
real Rust subprocess integration. Source/build revisions and executable digests are
different identities; retain both in deployment records.
