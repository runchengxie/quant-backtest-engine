#!/usr/bin/env python3
"""Deterministic synthetic session workload; all retained artifacts stay outside source.

Use a separately built `--example profile_sessions` binary. Each repetition uses a
fresh child. RSS is sampled from that child's /proc/PID/status, a lower bound on
its actual peak; it never uses the parent's cumulative child resource counter.
"""
import argparse
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def generate(sessions, symbols, times):
    if not (1 <= sessions <= 252 and 1 <= symbols <= 1024 and 2 <= times <= 1000):
        raise ValueError("sessions 1..252, symbols 1..1024, quote times 2..1000 required")
    names = [f"S{i:04}" for i in range(symbols)]
    request = dict(schema_version="engine_request.v2", currency="CNY", price_basis="raw",
                   initial_cash="100000000", fee_bps="10", enforce_t1=True,
                   instruments=[dict(symbol=n, price_precision=2, buy_lot=100) for n in names],
                   required_capabilities=["session_ledger"], sessions=[])
    day = date(2025, 1, 2)
    for index in range(sessions):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        # 01:30 UTC, synthetic minute ticks; explicit UTC nanoseconds.
        start = (day - date(1970, 1, 1)).days * 86400 * 10**9 + 5400 * 10**9
        quotes = [dict(symbol=n, ts_ns=start + tick * 60 * 10**9,
                       bid=f"{10 + (i % 10)}.{(index + tick) % 100:02}",
                       ask=f"{10 + (i % 10)}.{(index + tick) % 100:02}",
                       bid_size="1000000", ask_size="1000000", tradable=True,
                       limit_up=False, limit_down=False)
                  for tick in range(times) for i, n in enumerate(names)]
        orders = [dict(id=f"D{index:03}-{n}", symbol=n, information_ts_ns=start - 1,
                       side="buy" if index % 2 == 0 else "sell", quantity="100") for n in names]
        request["sessions"].append(dict(session_date=day.isoformat(), open_ts_ns=start,
            valuation_ts_ns=quotes[-1]["ts_ns"], quotes=quotes, orders=orders))
        day += timedelta(days=1)
    sizing = dict(schema_version="sizing_request.v1", currency="CNY",
        information_ts_ns=request["sessions"][0]["open_ts_ns"] - 1,
        cash="1000000", fee_bps="10", assets=[dict(symbol=n, held_quantity="0",
        reference_price=str(10 + i % 10), price_ts_ns=request["sessions"][0]["open_ts_ns"] - 2,
        target_weight=str((Decimal(1) / Decimal(symbols + 1)).quantize(Decimal("0.00000001"), rounding="ROUND_DOWN")), buy_lot=100) for i, n in enumerate(names)])
    return request, sizing


def check(result):
    ledger = result["daily_ledger"]
    for row in ledger:
        assert Decimal(row["cash"]) + Decimal(row["positions_value"]) == Decimal(row["nav"])
    assert sum((Decimal(row["commission"]) for row in ledger), Decimal(0)) == Decimal(result["total_commission"])
    assert ledger[-1]["cash"] == result["final_cash"]
    assert ledger[-1]["nav"] == result["final_nav"]
    for row in ledger:
        positions = [p for p in result["daily_positions"] if p["session_date"] == row["session_date"]]
        assert sum((Decimal(p["market_value"]) for p in positions), Decimal(0)) == Decimal(row["positions_value"])
    return dict(orders=len(result["orders"]), fills=len(result["fills"]), rejections=len(result["rejections"]),
                final_cash=result["final_cash"], final_nav=result["final_nav"], fees=result["total_commission"])


def invoke(binary, request, sizing, timeout):
    started = time.perf_counter()
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([str(binary), str(request), str(sizing)], stdout=output, stderr=errors)
        peak = 0
        timed_out = False
        while process.poll() is None:
            try:
                for line in Path(f"/proc/{process.pid}/status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        peak = max(peak, int(line.split()[1]))
            except FileNotFoundError:
                pass
            if time.perf_counter() - started > timeout:
                timed_out = True
                process.kill()
                break
            time.sleep(.01)
        process.wait()
        output.seek(0)
        errors.seek(0)
        record = dict(wall_seconds=time.perf_counter() - started, peak_rss_kib=peak,
                      timeout=timed_out, exit_code=process.returncode, stderr=errors.read().decode(errors="replace")[-2000:])
        if process.returncode == 0:
            try:
                profile = json.load(output)
                result = profile.pop("result")
                sizing_result = profile["sizing"].pop("result")
                record.update(profile=profile, result_sha256=hashlib.sha256(canonical(result)).hexdigest(),
                              sizing_sha256=hashlib.sha256(canonical(sizing_result)).hexdigest(), checks=check(result))
            except (ValueError, KeyError, TypeError, AssertionError, ArithmeticError) as error:
                record["validation_error"] = f"{type(error).__name__}: {error}"
        return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--build-profile", choices=["debug", "release"], required=True)
    parser.add_argument("--sessions", type=int, default=63)
    parser.add_argument("--symbols", type=int, default=100)
    parser.add_argument("--quote-times", type=int, default=241)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.output_dir.is_absolute() or args.output_dir.resolve().is_relative_to(root):
        parser.error("output directory must be absolute and outside repository")
    if args.repetitions < 3 or args.timeout <= 0:
        parser.error("at least 3 repetitions and positive timeout required")
    generation_started = time.perf_counter()
    request, sizing = generate(args.sessions, args.symbols, args.quote_times)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = [args.output_dir / name for name in ("request.json", "sizing.json")]
    for path, value in zip(paths, (request, sizing)):
        with path.open("xb") as stream:
            stream.write(canonical(value))
    del request, sizing
    report = dict(schema_version="representative_workload.v1", generator_version=1,
        revision=args.revision, build_profile=args.build_profile, binary_sha256=hashlib.sha256(args.engine.read_bytes()).hexdigest(),
        inputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        sessions=args.sessions, symbols=args.symbols, quote_times=args.quote_times,
        quote_rows=args.sessions * args.symbols * args.quote_times, expected_orders=args.sessions * args.symbols,
        input_generation_write_hash_seconds=time.perf_counter() - generation_started,
        memory_scope="engine child only; generator memory excluded; no enforced memory limit",
        timeout_seconds=args.timeout, rss_method="per-child /proc/PID/status VmRSS sampling; peak lower bound", rss_poll_seconds=.01,
        environment=dict(platform=platform.platform(), python=platform.python_version(), logical_cpus=os.cpu_count(),
                         threads={k: v for k, v in os.environ.items() if k in ("OMP_NUM_THREADS", "RAYON_NUM_THREADS")}),
        compiler=subprocess.check_output(["rustc", "--version"], text=True).strip(), runs=[])
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        report["environment"]["cpu_model"] = next((line.split(":", 1)[1].strip() for line in cpuinfo.read_text().splitlines() if line.startswith("model name")), "unknown")
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        report["environment"]["memory_kib_before_runs"] = {line.split(":")[0]: int(line.split()[1]) for line in meminfo.read_text().splitlines() if line.startswith(("MemTotal:", "MemAvailable:"))}
    report["environment"]["execution_threads"] = "one synchronous caller and one engine worker; no concurrent cases"
    for index in range(args.repetitions):
        record = invoke(args.engine, *paths, args.timeout)
        report["runs"].append(record)
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(dict(repetition=index, **record)), flush=True)
        if record["exit_code"] != 0 or "validation_error" in record:
            break
    good = len(report["runs"]) == args.repetitions and all(r["exit_code"] == 0 and "validation_error" not in r for r in report["runs"])
    if good:
        good = all(r["checks"]["orders"] == args.sessions * args.symbols and r["checks"]["fills"] == args.sessions * args.symbols and r["checks"]["rejections"] == 0 for r in report["runs"])
        good = good and len({r["result_sha256"] for r in report["runs"]}) == 1 and len({r["sizing_sha256"] for r in report["runs"]}) == 1
    return int(not good)


if __name__ == "__main__":
    raise SystemExit(main())
