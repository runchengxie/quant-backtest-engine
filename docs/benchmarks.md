# Synthetic CLI batch benchmarks

[中文](benchmarks.zh-CN.md)

Independent subprocesses can execute these tiny synthetic requests concurrently.
This experiment measures CLI batch execution, including process startup, fixture
reading, engine work and JSON output. It does not establish production capacity,
compile speed, or a performance comparison with another implementation.

Run from a source checkout with a trusted, prebuilt binary:

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
and nearest-rank p50/p95 latency. Latency starts when a worker starts a subprocess;
it excludes waiting for a worker. Throughput counts successful jobs only.
Canonical JSON result digests must match the same fixture's warmup across all jobs.
Nonzero exits, timeouts, invalid JSON and digest mismatches are explicit errors;
the script writes the report and exits nonzero if any occur. Timed-out process
groups are killed. Failure details can contain local paths; review before sharing.

On Linux, GNU `/usr/bin/time`, when available, records each child's peak resident
set in KiB. This is not simultaneous batch peak memory; adding child peaks does
not estimate that quantity. Missing measurement support is recorded explicitly.

## Observed experiment, 2026-10-31

The pinned executable came from source
`3ee74bfa21d743e595ce61d0ac06b97dd588ebd6`, debug profile, 38,252,752 bytes,
SHA-256 `9ed68e44f6eb9f8861b3c57ede6300e23db5d6fd5d8f80f7afbb2ecdae6c18c7`.
Host: Linux x86-64, Intel Core i5-4690K at 3.50 GHz, four logical CPUs,
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
The capability probe is only a rough process/serialization reference; subtracting
it does not isolate engine compute time. Use representative larger synthetic
workloads, repeated runs and a release build before selecting deployment limits.
No release result or language baseline was measured here. Scheduling and resource
limits belong to the caller; this script does not add an engine task service.
