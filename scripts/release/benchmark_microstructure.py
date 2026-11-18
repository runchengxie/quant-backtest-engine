#!/usr/bin/env python3
"""Compare installed Python/native synthetic workloads; require exact result parity."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def rows(count, seed):
    rng = random.Random(seed)
    return [
        (i, rng.choice((-1, 1)), rng.randrange(97, 104), rng.randrange(1, 100), str(i))
        for i in range(count)
    ]


def matching(backend, events):
    from quant_backtest_core.microstructure.matching import MatchingEngine

    engine = MatchingEngine(backend)
    results = [
        engine.apply_order(oid, side, price, qty) for _, side, price, qty, oid in events
    ]
    return (
        [None if r is None else asdict(r) for r in results],
        engine.lob.best_bid(),
        engine.lob.best_ask(),
    )


def replay(backend, events):
    from quant_backtest_core.microstructure.matching import MatchingEngine
    from quant_backtest_core.microstructure.replay import ReplaySession

    session = ReplaySession(MatchingEngine(backend), (95, 100), (105, 100))
    for row in events:
        session.add_background(*row)
    session.run()
    return ([asdict(t) for t in session.ticks], [asdict(f) for f in session.fills])


def ordered(backend, events):
    from quant_backtest_core.microstructure.ordering import sort_simulator_events
    from quant_backtest_core.microstructure.pack import SimulatorEvent

    records = [
        SimulatorEvent(
            t // 8,
            "order",
            order_id=oid,
            side=side,
            price=p,
            volume=q,
            channel="A",
            sequence=len(events) - t,
            source_index=t,
        )
        for t, side, p, q, oid in events
    ]
    return [asdict(e) for e in sort_simulator_events(records, backend=backend)]


def measure(fn, repetitions):
    # Warm both imports and code paths. Alternate order to reduce ordering bias.
    expected = digest(fn("python"))
    if digest(fn("rust")) != expected:
        raise ValueError("Python/native result mismatch before timing")
    samples = {"python": [], "rust": []}
    for i in range(repetitions):
        for backend in ("python", "rust") if i % 2 == 0 else ("rust", "python"):
            start = time.perf_counter()
            result = fn(backend)
            elapsed = time.perf_counter() - start
            if digest(result) != expected:
                raise ValueError(f"{backend} nondeterministic result")
            samples[backend].append(elapsed)
    medians = {b: statistics.median(s) for b, s in samples.items()}
    return {
        "result_sha256": expected,
        "seconds": samples,
        "median_seconds": medians,
        "python_over_rust": medians["python"] / medians["rust"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--paths", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if output.is_relative_to(root) or output.exists():
        parser.error("output must be a new external file")
    if not (
        1 <= args.events <= 100000
        and 1 <= args.paths <= 32
        and 1 <= args.repetitions <= 11
    ):
        parser.error("events 1..100000, paths 1..32, repetitions 1..11 required")
    workload = rows(args.events, args.seed)
    paths = [rows(args.events, args.seed + i) for i in range(args.paths)]
    # Retain hashes of installed implementation bytes as well as source revision.
    installed = {}
    for name in ("quant-backtest-core", "quant-microstructure-core"):
        dist = metadata.distribution(name)
        files = {
            str(f): hashlib.sha256(Path(dist.locate_file(f)).read_bytes()).hexdigest()
            for f in dist.files or []
            if str(f).endswith((".py", ".pyi", ".so"))
        }
        installed[name] = {"version": dist.version, "files": files}
    result = {
        "schema": "engine-microstructure-benchmark.v1",
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=root, text=True
            )
        ),
        "python": sys.version,
        "platform": platform.platform(),
        "timing_scope": "End-to-end public calls, allocation and result projection included; hashing excluded. Sequential independent paths, no parallelism.",
        "assumptions": "Synthetic unique order IDs, integer price ticks/shares, no account ledger, latency or calibration. Local timings do not establish market capacity.",
        "events": args.events,
        "paths": args.paths,
        "repetitions": args.repetitions,
        "seed": args.seed,
        "workload_sha256": digest(paths),
        "installed": installed,
        "cases": {},
    }
    for name, fn in [
        ("per_order_with_fills", lambda b: matching(b, workload)),
        ("batch_replay_with_fills", lambda b: replay(b, workload)),
        ("independent_paths", lambda b: [replay(b, p) for p in paths]),
        ("event_ordering", lambda b: ordered(b, workload)),
    ]:
        result["cases"][name] = measure(fn, args.repetitions)
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps({name: r["median_seconds"] for name, r in result["cases"].items()})
    )


if __name__ == "__main__":
    main()
