# Synthetic CLI batch benchmarks

[中文](benchmarks.zh-CN.md)

Independent subprocesses can execute these tiny synthetic requests concurrently.
This experiment measures CLI batch execution, including process startup, fixture
reading, engine work and JSON output. It does not establish production capacity,
compile speed, or a performance comparison with another implementation.

Run from a source checkout with a trusted, prebuilt binary.

```bash
python project_tools/benchmark.py \
  --engine /absolute/path/to/quant-backtest-engine \
  --engine-revision FULL_SOURCE_COMMIT --build-profile debug \
  --output /absolute/external/path/benchmark.json \
  --jobs 24 --concurrency 1,2,4 --timeout 30
```

The output must be outside the checkout and must not already exist. Each fixture
gets a separate warmup, followed by independent batches at each concurrency.
The capabilities probe is separate from workload timings. Results include binary
SHA-256 and size, fixture hashes, environment, individual latencies, wall throughput,
and nearest-rank p50/p95 latency. Latency starts when a worker starts a subprocess.
It excludes waiting for a worker. Throughput counts successful jobs only.
Canonical JSON result digests must match the same fixture's warmup across all jobs.
Nonzero exits, timeouts, invalid JSON and digest mismatches are explicit errors.
The script writes the report and exits nonzero if any occur. Timed-out process
groups are killed. Failure details can contain local paths. Review before sharing.

On Linux, GNU `/usr/bin/time`, when available, records each child's peak resident
set in KiB. This is not simultaneous batch peak memory. Adding child peaks does
not estimate that quantity. Missing measurement support is recorded explicitly.

## Observed experiment, 2026-10-31

The pinned executable came from source
`3ee74bfa21d743e595ce61d0ac06b97dd588ebd6`, debug profile, 38,252,752 bytes,
SHA-256 `9ed68e44f6eb9f8861b3c57ede6300e23db5d6fd5d8f80f7afbb2ecdae6c18c7`.
The host ran Linux x86-64, Intel Core i5-4690K at 3.50 GHz, four logical CPUs,
Python 3.14.8. GNU `/usr/bin/time` was absent, so RSS was not measured.
Both committed fixtures were tested with 12 and 24 jobs per batch and concurrency
1, 2 and 4. All jobs succeeded and matched their fixture's warmup digest.

| Jobs | Fixture | Concurrency | Batch seconds | Jobs/s | p50 / p95 ms |
| --- | --- | --- | --- | --- | --- |
| 12 | roundtrip.json | 1 | 0.178 | 67.6 | 14.4 / 15.9 |
| 12 | roundtrip.json | 2 | 0.106 | 112.7 | 16.7 / 18.8 |
| 12 | roundtrip.json | 4 | 0.078 | 153.6 | 20.2 / 34.5 |
| 12 | sessions.json | 1 | 0.205 | 58.4 | 16.9 / 17.8 |
| 12 | sessions.json | 2 | 0.156 | 77.0 | 22.3 / 42.9 |
| 12 | sessions.json | 4 | 0.138 | 87.1 | 38.9 / 56.0 |
| 24 | roundtrip.json | 1 | 0.384 | 62.4 | 15.3 / 21.0 |
| 24 | roundtrip.json | 2 | 0.229 | 104.7 | 17.3 / 28.1 |
| 24 | roundtrip.json | 4 | 0.151 | 158.9 | 23.1 / 36.3 |
| 24 | sessions.json | 1 | 0.417 | 57.6 | 17.2 / 18.3 |
| 24 | sessions.json | 2 | 0.264 | 90.9 | 19.7 / 30.2 |
| 24 | sessions.json | 4 | 0.182 | 132.2 | 27.5 / 39.0 |

These subsecond batches show that this host can overlap independent CLI jobs.
They are sensitive to startup costs, scheduling and other host activity. The
12-job and 24-job runs are separate samples, not statistical confidence intervals.
The capability probe is only a rough process/serialization reference. Subtracting
it does not isolate engine compute time. Use representative larger synthetic
workloads, repeated runs and a release build before selecting deployment limits.
No release result or language baseline was measured here. Scheduling and resource
limits belong to the caller. This script does not add an engine task service.

## Larger deterministic workloads

The separate development example `profile_sessions` adds opt-in wall phases to
the same session execution implementation without changing either wire schema.
The commands and measurement details are [below](#run-the-session-profiler). Default dimensions are 63
synthetic weekdays × 100 symbols × 241 minute timestamps = 1,518,300 quote rows.
Each session alternates buy/sell intents for every symbol. This covers multi-asset
loading, repeated matching, upstream accounting, and daily snapshot extraction.
It does not cover real market data, corporate actions, intraday portfolio decisions,
or large competing order books.

The runner keeps versioned synthetic inputs and their hashes, at least three
fresh-child repetitions, independent sizing timings and digests, and actual order
and fill counts. It verifies cash plus positions equals NAV, summed daily fees,
and position values against the daily ledger. A separate small invocation is the
warmup. Do not mix warmup or debug measurements into release comparisons.

Wall phases separate validation/cloning, header and engine setup, current-session
input preparation and quote conversion/loading, replay, daily snapshots/data
clearing, and finalization. Upstream matching and accounting share the replay
phase. Child RSS samples every 10 ms give a per-run peak lower bound, excluding
Python input generation. The default 6144 MiB sampled child guard stops and
records an over-budget child, but is not an operating-system memory limit and
cannot catch every spike. There is no per-phase
allocation attribution. Input read/decode and result encoding are measured
separately. Envelope encoding, output transfer and polling remain in full wall
time. Results describe the specified host and workload, not production capacity.

## Broad universe and sparse execution

`project_tools/sparse_workload.py` distinguishes the registered universe from
predetermined orders. Its synthetic book trades only `--active` names each
session, buying one group and selling that same group in the following session,
then rotating to another group. This is twenty orders per session, not a claim
that every daily rebalance of a twenty-name portfolio requires only twenty orders.
The example also measures a separate initial sizing probe, not full-market alpha
scoring, risk estimation or portfolio optimization.

The `all` mode supplies every minute quote. `orders-and-valuation` retains every
active name's minute quotes and a fresh valuation-boundary quote for every
registered name in every session. This is valid only for the demonstrated
fixed-intent execution consumer with no idle-security intraday signal, risk or
cross-impact consumer. Never remove observations required to generate the orders.
Synthetic marks are not a substitute for missing historical or suspended-stock
valuation evidence. A small full-versus-routed financial-result comparison must
precede interpreting a routed benchmark.

The default two-million-quote preallocation budget writes a plan and returns an
explicit non-execution status for an oversized full-market JSON request. It does
not silently truncate instruments, days or quotes. Child RSS remains sampled and
generator memory remains excluded. Quote count is not an OS memory guarantee.
For example, `--symbols 6000 --active 20 --sessions 63 --quote-times 241` is a
synthetic size illustration, not a current listed-stock count. Both modes use
one-minute spacing. Fewer timestamps shorten the session, not its sampling rate.

## Pending-intent indexing, 2026-11-04

Session replay indexes pending intents by session and instrument. Each quote
checks only that bucket, retaining request order and the strict
`information_ts_ns < quote.ts_ns` boundary. Eligible intents are consumed in one
pass without shifting the remaining quarter's orders. Account reads, cash and
fee admission, T+1 reservations, quote permissions and upstream IOC matching
continue through the same execution path. `strategy_pending_checks` counts
individual intent eligibility examinations, including the initial eligibility
probe and the subsequent admission pass. Map lookups are not counted.

A release comparison against `c33434d4a5f96eb947d71a751ef25bd434dd3d5e`
used Rust 1.99.1 on Linux x86-64. Each binary had a separate warmup followed by
three fresh-child repetitions of each deterministic workload. Inputs came from
`generate_sparse(8, 120, 6, 30, "all", 100000)` and `generate(8, 20, 20)` in
the existing workload tools, using the nonwire `profile_sessions` example.

| Workload | Quotes / orders | Pending checks before / after | Full wall seconds before / after (range) |
| --- | --- | --- | --- |
| Sparse, eight sessions | 28,800 / 48 | 605,448 / 96 | 0.256-0.365 / 0.257-0.416 |
| Dense, eight sessions | 3,200 / 160 | 225,840 / 320 | 0.087-0.097 / 0.084-0.092 |

All complete financial result objects matched before and after in every run.
Canonical result SHA-256 values were
`c9f864adab63e77f0e5ed909738eb3d201f3705c64774cbc12789e0840a09c7d`
(sparse) and
`56a6d73ef65d7959c43d1b4d06928924faa16f680d010eeae1ab00a9933beec2`
(dense). Both workloads filled every order with no rejections. Account reads
remained 48 and 160 respectively. The operation-count regression also keeps 103
unsubmitted intents across two sessions and two instruments. Eight quotes inspect
206 matching-bucket intents, compared with 824 global examinations before indexing.

These small runs establish fewer pending-intent examinations and economic equality,
not a wall-time speedup or full-market capacity. Wall ranges overlap and include
input decoding, setup, replay and output. Pending intents within one bucket are
still scanned until eligible. Rule storage, whole-request cloning, quote loading,
upstream accounting and memory limits are unchanged. No quarter-scale run or
streaming input redesign is included in this change.

## Run the session profiler

For larger deterministic synthetic workloads, build the opt-in development runner
with `cargo build --locked --release --example profile_sessions`, setting
`CARGO_TARGET_DIR` outside the repository. Then run.

```sh
python3 project_tools/profile_workload.py --engine /absolute/target/release/examples/profile_sessions \
  --output-dir /absolute/data/unique-workload-run --revision "$(git rev-parse HEAD)" \
  --build-profile release --sessions 63 --symbols 100 --quote-times 241
```

This is 1,518,300 quote rows across 63 synthetic weekdays, with one alternating
buy/sell intent per symbol per session. It is a representative synthetic workload,
not a market-data replay or a capacity guarantee. Start with a small separate
warmup (for example 2 sessions, 3 symbols, 4 quote times), then increase the scale.
Each command records at least three fresh-process repetitions, input and result
hashes, actual sizing time, ledger invariants, wall phases, and sampled child RSS.
Use unique external output directories. Existing inputs are never overwritten.

The profile example uses the same execution implementation as `run_sessions`.
With owned incremental session input, `setup_seconds` covers engine, instrument
and strategy header setup. `quote_conversion_load_seconds` includes loading the
current session's pending intents and quote rules, quote conversion and upstream
loading. Per-session incremental validation is included in overall execution time
outside these named phases. `validation_clone_seconds` continues to measure the
compatibility wrapper's full-request validation and cloning.

Earlier build receipts that preload all sessions' rules and intents include that
work in setup. Their phase definitions remain attached to those source revisions.
Compare phase values only with their implementation revision and definitions;
the same field names do not establish equivalent phase boundaries.

 Upstream replay includes
matching and accounting together. Nested strategy timers measure rule lookup,
instrument lookup, owned account snapshot reads (`strategy_cache_seconds`), and
pending-intent admission/submission (`strategy_pending_seconds`). The latter
includes upstream work called synchronously by submission. Counters record quote
callbacks, pending entries inspected, and account snapshot reads. These timers
overlap replay and must not be added to it. Normal execution does not read clocks.
Quotes without an eligible current-session intent skip adapter rule/cache reads.
All quotes still pass through upstream replay for matching and valuation.
Snapshot/ledger extraction and finalization have separate timers. Execution time
also includes validation, request cloning and thread lifecycle overhead, so phase
sums need not equal execution time. Result serialization measures compact result
encoding only, excluding diagnostic-envelope encoding and stdout transfer. RSS is
a 10 ms `/proc` sample maximum, hence a lower bound, not an exact peak or phase
allocation measurement. Compare only identical build profiles and fixed input
hashes. No timing threshold is used in tests.

The workload generator runs in the Python parent. Its memory is excluded from
child RSS. Workload dimensions and child timeout are bounded, but this runner
does not enforce an operating-system memory limit. It kills and records a child
whose sampled RSS exceeds `--max-rss-mib` (default 6144 MiB). Sampling may miss
a short spike and does not bound parent-generator memory. Snapshot/ledger time includes
upstream data clearing. Full child wall time includes diagnostic encoding and
output transfer. Python polling can add up to one sampling interval. The sizing
probe is independent of replay orders and is not represented as execution evidence.
