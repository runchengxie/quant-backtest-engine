#!/usr/bin/env python3
"""Measure independent synthetic CLI jobs; outputs are external research artifacts."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import tempfile
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def invoke(engine, command, timeout):
    started = time.perf_counter()
    record = {"command": command}
    # GNU time reports the individual CLI child's maximum resident set in KiB.
    with tempfile.TemporaryDirectory(prefix="engine-benchmark-") as temporary:
        rss = Path(temporary) / "rss"
        argv = [str(engine), *command]
        if platform.system() == "Linux" and Path("/usr/bin/time").exists():
            argv = ["/usr/bin/time", "-f", "%M", "-o", str(rss), *argv]
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise
            result = subprocess.CompletedProcess(
                argv, process.returncode, stdout, stderr
            )
            record.update(
                exit_code=result.returncode,
                stderr=result.stderr.decode(errors="replace")[-4000:],
            )
            if result.returncode:
                record["error"] = "nonzero_exit"
            else:
                try:
                    canonical = json.dumps(
                        json.loads(result.stdout), sort_keys=True, separators=(",", ":")
                    ).encode()
                    record["result_sha256"] = digest(canonical)
                except (ValueError, UnicodeError):
                    record["error"] = "invalid_json"
            if rss.exists():
                try:
                    record["peak_rss_kib"] = int(
                        rss.read_text().strip().splitlines()[-1]
                    )
                except ValueError:
                    pass
        except subprocess.TimeoutExpired:
            record["error"] = "timeout"
        except OSError as error:
            record.update(error="spawn_failed", detail=str(error))
    record["wall_seconds"] = time.perf_counter() - started
    return record


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--engine-revision", required=True)
    parser.add_argument(
        "--build-profile", choices=["debug", "release", "unknown"], required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=24)
    parser.add_argument("--concurrency", default="1,2,4")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.engine.is_absolute() or not args.engine.is_file():
        parser.error("--engine must be an existing absolute binary path")
    if not args.output.is_absolute() or args.output.resolve().is_relative_to(root):
        parser.error(
            "--output must be an explicit absolute path outside the repository"
        )
    try:
        concurrency = [int(value) for value in args.concurrency.split(",")]
        if (
            not concurrency
            or min(concurrency) < 1
            or args.jobs < 1
            or args.timeout <= 0
        ):
            raise ValueError
    except ValueError:
        parser.error("jobs, concurrency and timeout must be positive")
    fixtures = [
        root / "fixtures" / name for name in ("roundtrip.json", "sessions.json")
    ]
    report = {
        "schema_version": "synthetic_cli_benchmark.v1",
        "engine_revision": args.engine_revision,
        "engine_sha256": digest(args.engine.read_bytes()),
        "engine_bytes": args.engine.stat().st_size,
        "build_profile": args.build_profile,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
        },
        "rss_measurement": "per_child_max_rss_kib"
        if platform.system() == "Linux" and Path("/usr/bin/time").exists()
        else "unavailable: GNU /usr/bin/time missing or non-Linux",
        "jobs_per_batch": args.jobs,
        "timeout_seconds": args.timeout,
        "fixtures": {p.name: digest(p.read_bytes()) for p in fixtures},
        "batches": [],
    }
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        report["environment"]["cpu_model"] = next(
            (
                line.split(":", 1)[1].strip()
                for line in cpuinfo.read_text().splitlines()
                if line.startswith("model name")
            ),
            "unknown",
        )
    report["capabilities_probe"] = invoke(args.engine, ["capabilities"], args.timeout)
    report["warmup"] = {
        p.name: invoke(args.engine, ["run", str(p)], args.timeout) for p in fixtures
    }
    failed = "error" in report["capabilities_probe"] or any(
        "error" in value for value in report["warmup"].values()
    )
    for fixture in fixtures:
        expected = report["warmup"][fixture.name].get("result_sha256")
        for workers in concurrency:
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                records = list(
                    pool.map(
                        lambda _: invoke(
                            args.engine, ["run", str(fixture)], args.timeout
                        ),
                        range(args.jobs),
                    )
                )
            elapsed = time.perf_counter() - started
            for record in records:
                if "error" not in record and record.get("result_sha256") != expected:
                    record["error"] = "digest_mismatch"
            successes = sum("error" not in record for record in records)
            failed |= successes != args.jobs
            latency = [r["wall_seconds"] for r in records]
            report["batches"].append(
                {
                    "fixture": fixture.name,
                    "concurrency": workers,
                    "wall_seconds": elapsed,
                    "successful_jobs": successes,
                    "failed_jobs": args.jobs - successes,
                    "successful_jobs_per_second": successes / elapsed,
                    "latency_p50_seconds": percentile(latency, 0.5),
                    "latency_p95_seconds": percentile(latency, 0.95),
                    "jobs": records,
                }
            )
    # Paths are local execution inputs; omit them from retained, portable records.
    for record in [
        report["capabilities_probe"],
        *report["warmup"].values(),
        *(r for batch in report["batches"] for r in batch["jobs"]),
    ]:
        record["command"] = [Path(part).name for part in record["command"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({"output": str(args.output), "failed": bool(failed)}))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
