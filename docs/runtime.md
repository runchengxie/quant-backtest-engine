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


## Static preflight

Before job insertion, runtime agent plans can invoke `validate -` through the
same held, SHA-256-verified executable inode. The validator reuses `Request` serde
parsing and `Request::validate`; it performs no simulation. It reads no more than
1 MiB plus one byte and emits an exact-byte SHA-256 receipt only on success:

```json
{"schema_version":"engine_validation.v1","request_schema":"engine_request.v1","validator_version":1,"valid":true,"input_sha256":"<64 lowercase hex characters>"}
```

The validator contract version is independent of backend and simulation capability
versions. The CLI `capabilities` object adds `validator_version: 1`; the existing
simulation capability list, `run`, `size` and session operations retain their contracts.
Validation rejects unsupported semantics and malformed/oversized input with exit 2
and empty stdout. I/O or internal failure uses exit 1. Deploy an immutable binary:
holding a descriptor prevents pathname replacement, but does not prevent in-place
writes to the executable inode. Consumers must bound subprocess time and both
output streams and verify receipt identity before trusting preflight.


## Session jobs and Python analytics

Runtime [PR #39](https://github.com/runchengxie/quant-backtest-runtime/pull/39)
adds opt-in v6 `nautilus.session_replay`, consuming `engine_request.v2` and
publishing `quant.engine_job_result.v2`. It verifies daily flows and binds marks
to valuation quotes before publication. Job success still permits denied orders.

The platform's explicit
[session client](https://github.com/runchengxie/quant-platform/pull/170)
verifies selected executable bytes and maps the session output for Python
analytics. It retains `execution_aware=False`; existing Python backends remain
default. See [tested combinations](capabilities.md) and the
[weight-to-ledger walkthrough](tutorial.md).
