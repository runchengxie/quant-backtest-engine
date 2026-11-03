#!/usr/bin/env python3
"""Synthetic broad universe with a small, predetermined execution book.

Routing is valid only for this fixed-intent execution-only consumer, with no
intraday signal/risk/impact consumer of idle securities' quotes. This is not a
full-market research pipeline or historical A-share calibration.
"""
import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from profile_workload import canonical, generate, invoke


def workload_plan(sessions, symbols, active, times, routing, max_quotes):
    values = (sessions, symbols, active, times, max_quotes)
    if any(type(v) is not int for v in values):
        raise ValueError("integer dimensions required")
    if not (1 <= sessions <= 252 and 1 <= symbols <= 10000
            and 1 <= active <= min(symbols, 1024) and 2 <= times <= 1000
            and max_quotes > 0):
        raise ValueError("invalid workload dimensions")
    if routing not in {"all", "orders-and-valuation"}:
        raise ValueError("unknown quote routing")
    rows = sessions * (symbols * times if routing == "all"
                       else symbols + active * (times - 1))
    return dict(sessions=sessions, universe_symbols=symbols,
                active_order_symbols_per_session=active, timestamps_per_session=times,
                routing=routing, quote_rows=rows, orders=sessions * active,
                max_quotes=max_quotes, over_quote_budget=rows > max_quotes,
                timestamp_spacing_seconds=60, session_span_minutes=times - 1)


def _quote(symbol, index, tick, day_index, start):
    price = f"{10 + index % 10}.{(day_index + tick) % 100:02}"
    return dict(symbol=symbol, ts_ns=start + tick * 60 * 10**9,
                bid=price, ask=price, bid_size="1000000", ask_size="1000000",
                tradable=True, limit_up=False, limit_down=False)


def generate_sparse(sessions, symbols, active, times, routing, max_quotes):
    plan = workload_plan(sessions, symbols, active, times, routing, max_quotes)
    if plan["over_quote_budget"]:
        raise ValueError("quote budget exceeded before allocation")
    # Reuse the existing schema and independent sizing probe, not a simulator.
    request, sizing = generate(sessions, active, times)
    names = [f"S{i:04}" for i in range(symbols)]
    request["instruments"] = [dict(symbol=n, price_precision=2, buy_lot=100) for n in names]
    request["sessions"] = []
    day = date(2025, 1, 2)
    for day_index in range(sessions):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        start = (day - date(1970, 1, 1)).days * 86400 * 10**9 + 5400 * 10**9
        # A fixed, known-before-open pair of buy/sell days; twenty orders/day
        # is distinct from rotating a twenty-name portfolio every single day.
        selected = sorted({((day_index // 2) * active + j) % symbols for j in range(active)})
        quotes = []
        for tick in range(times):
            indices = range(symbols) if routing == "all" or tick == times - 1 else selected
            quotes.extend(_quote(names[i], i, tick, day_index, start) for i in indices)
        orders = [dict(id=f"D{day_index:03}-{names[i]}", symbol=names[i],
                       information_ts_ns=start - 1,
                       side="buy" if day_index % 2 == 0 else "sell", quantity="100")
                  for i in selected]
        request["sessions"].append(dict(session_date=day.isoformat(), open_ts_ns=start,
            valuation_ts_ns=start + (times - 1) * 60 * 10**9, quotes=quotes, orders=orders))
        day += timedelta(days=1)
    return request, sizing


def validate_run(record, expected_orders):
    if record["exit_code"] != 0 or "validation_error" in record:
        return False
    checks = record["checks"]
    if checks["orders"] != expected_orders or checks["fills"] != expected_orders or checks["rejections"]:
        record["validation_error"] = "unexpected synthetic order/fill counts"
        return False
    # Operation-count regression, not a flaky CI wall-time threshold. Every
    # parent here is admitted on exactly one quote callback and then removed.
    reads = record["profile"]["phases"].get("strategy_cache_reads")
    if reads is None or reads > expected_orders:
        record["validation_error"] = "account snapshot operation budget exceeded or unavailable"
        return False
    record["operation_regression"] = dict(account_snapshot_reads=reads,
                                         maximum_for_fixed_intents=expected_orders)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--engine-source-revision", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sessions", type=int, default=63)
    parser.add_argument("--symbols", type=int, default=100)
    parser.add_argument("--active", type=int, default=20)
    parser.add_argument("--quote-times", type=int, default=241)
    parser.add_argument("--routing", choices=["all", "orders-and-valuation"], default="all")
    parser.add_argument("--max-quotes", type=int, default=2_000_000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-rss-mib", type=int, default=6144)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.output_dir.is_absolute() or args.output_dir.resolve().is_relative_to(root):
        parser.error("output must be an explicit new directory outside the repository")
    if args.repetitions < 3 or args.timeout <= 0 or args.max_rss_mib <= 0:
        parser.error("three repetitions and positive resource budgets required")
    try:
        plan = workload_plan(args.sessions, args.symbols, args.active, args.quote_times,
                             args.routing, args.max_quotes)
    except ValueError as error:
        parser.error(str(error))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(schema_version="sparse_execution_workload.v1", plan=plan,
                  source_revision=subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  engine_source_revision=args.engine_source_revision,
                  synthetic_only=True, fixed_orders_known_before_open=True,
                  alpha_and_market_scan_measured=False,
                  routing_scope="execution-only; no intraday idle-security consumer",
                  memory_scope="sampled child lower bound; parent generator excluded",
                  python=platform.python_version(), runs=[])
    path = args.output_dir / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    if plan["over_quote_budget"]:
        report["status"] = "not_executed_quote_budget"
        path.write_text(json.dumps(report, indent=2) + "\n")
        return 2
    binary_hash = hashlib.sha256(args.engine.read_bytes()).hexdigest()
    started = time.perf_counter()
    request, sizing = generate_sparse(args.sessions, args.symbols, args.active,
                                     args.quote_times, args.routing, args.max_quotes)
    inputs = [args.output_dir / "request.json", args.output_dir / "sizing.json"]
    for item, value in zip(inputs, (request, sizing)):
        item.write_bytes(canonical(value))
    del request, sizing
    report.update(binary_sha256=binary_hash,
                  input_generation_write_seconds=time.perf_counter() - started,
                  input_sha256={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs},
                  input_bytes={f.name: f.stat().st_size for f in inputs})
    path.write_text(json.dumps(report, indent=2) + "\n")
    for index in range(args.repetitions):
        record = invoke(args.engine, *inputs, args.timeout, args.max_rss_mib * 1024)
        valid = validate_run(record, plan["orders"])
        report["runs"].append(record)
        report["status"] = "running" if valid else "failed"
        path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(dict(repetition=index, **record)), flush=True)
        if not valid:
            break
    successful = len(report["runs"]) == args.repetitions and all(
        validate_run(r, plan["orders"]) for r in report["runs"])
    if successful:
        successful = len({r["result_sha256"] for r in report["runs"]}) == 1
    if hashlib.sha256(args.engine.read_bytes()).hexdigest() != binary_hash:
        report["binary_changed"] = True
        successful = False
    report["status"] = "complete_execution_only" if successful else "failed"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return int(not successful)


if __name__ == "__main__":
    raise SystemExit(main())
