"""Export synthetic queue evidence from the standalone matching owner."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["project_tools/export_event_demo.py",
           "core/src/quant_backtest_core/microstructure/latency_replay.py",
           "core/src/quant_backtest_core/microstructure/matching.py",
           "core/src/quant_backtest_core/microstructure/pack.py",
           "core/src/quant_backtest_core/microstructure/ordering.py"]


def exact(value):
    if type(value) is int:
        return str(value)
    if isinstance(value, (list, tuple)):
        return [exact(v) for v in value]
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    return value


def produce():
    sys.path.insert(0, str(ROOT / "core/src"))
    sys.path.insert(0, str(ROOT / "python/src"))
    from quant_backtest_core.microstructure.latency_replay import Command, replay_commands
    def order(key, time, sequence, side, price, quantity, delay=0):
        return Command(key, "order", time, delay, 20, sequence, key, side, price, quantity)
    cases = {}
    for key, delay in [("timely", 1), ("late", 150)]:
        commands = [order("ahead", 100, 0, 1, 100, 5), order("lower", 100, 1, 1, 99, 10),
                    order("own", 110, 2, 1, 100, 3, delay), order("seller", 200, 3, -1, 99, 7)]
        cases[key] = exact(asdict(replay_commands(commands)))
    for key, delay in [("cancel-fast", 0), ("cancel-late", 100)]:
        commands = [order("own", 100, 0, 1, 100, 3),
                    Command("cancel", "cancel", 150, delay, 20, 1, "own"),
                    order("seller", 200, 2, -1, 100, 3)]
        cases[key] = exact(asdict(replay_commands(commands)))
    return {"schema": "queue-demo.v1", "scope": "synthetic_matching_only",
            "units": {"price": "CNY_cent", "quantity": "raw_share", "clock": "elapsed_ns"},
            "sources": {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in SOURCES},
            "cases": cases}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    p.add_argument("--output", type=Path, default=ROOT/"web/src/data/queue-demo.json")
    a = p.parse_args()
    raw = json.dumps(produce(), ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if a.check:
        if a.output.read_text() != raw:
            raise ValueError("queue demo differs from current owner-produced evidence")
        print("Queue demo owner outputs and source hashes verified")
    else:
        a.output.write_text(raw)

if __name__ == "__main__":
    main()
