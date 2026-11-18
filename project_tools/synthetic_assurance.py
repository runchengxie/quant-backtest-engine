"""Reproducible synthetic assurance. Outputs are task-specific, never calibrated capacity."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
T = 1_735_689_600_000_000_000


def client_for(binary):
    from quant_backtest_engine import EngineClient

    return EngineClient(
        binary.resolve(), hashlib.sha256(binary.read_bytes()).hexdigest()
    )


def native_lot_checks(client, seed, cases):
    from quant_backtest_core.planning.discrete_oracle import enumerate_lot_portfolios

    rng = random.Random(seed)
    largest_gap = Fraction(0)
    for _ in range(cases):
        n = rng.randint(1, 3)
        request = {
            "schema_version": "engine_lot_request.v1",
            "prices": [str(Decimal(rng.randint(1, 200)) / 100) for _ in range(n)],
            "target_quantities": [
                str(Decimal(rng.randint(0, 40)) / 4) for _ in range(n)
            ],
            "max_lots": [rng.randint(0, 4) for _ in range(n)],
            "lot_sizes": [rng.randint(1, 3) for _ in range(n)],
            "cash_budget": str(Decimal(rng.randint(0, 2000)) / 100),
            "minimum_commission": str(Decimal(rng.randint(0, 10)) / 100),
            "proportional_commission": "0.001",
            "max_states": 100000,
            "candidate_quantities": [0] * n,
        }
        result = client.plan_lots(request)
        reference = enumerate_lot_portfolios(
            prices=list(map(Decimal, request["prices"])),
            target_quantities=list(map(Decimal, request["target_quantities"])),
            max_lots=request["max_lots"],
            lot_sizes=request["lot_sizes"],
            cash_budget=Decimal(request["cash_budget"]),
            minimum_commission=Decimal(request["minimum_commission"]),
            proportional_commission=Decimal(request["proportional_commission"]),
            candidate_quantities=request["candidate_quantities"],
        )
        assert tuple(result["quantities"]) == reference.quantities
        expected = sum(
            (
                p * q
                + (
                    max(
                        Fraction(request["minimum_commission"]),
                        Fraction(request["proportional_commission"]) * p * q,
                    )
                    if q
                    else 0
                )
                for p, q in zip(map(Fraction, request["prices"]), result["quantities"])
            ),
            Fraction(),
        )
        loss = sum(
            (
                (Fraction(q) - Fraction(t)) ** 2
                for q, t in zip(result["quantities"], request["target_quantities"])
            ),
            Fraction(),
        )
        assert (
            Fraction(result["spent"]) == expected
            and Fraction(result["objective"]) == loss
        )
        assert result["evaluated"] == reference.evaluated
        largest_gap = max(largest_gap, Fraction(result["candidate_gap"]))
    return {
        "cases": cases,
        "seed": seed,
        "reference": "retained Python Fraction exhaustive oracle",
        "largest_zero_candidate_gap": str(largest_gap),
    }


def inventory_checks(seed, cases):
    from quant_backtest_core.planning.discrete_inventory import (
        DiscreteInventoryRequest,
        solve_discrete_inventory,
    )

    rng = random.Random(seed)
    largest_gap = Fraction(0)
    for _ in range(cases):
        n = 2
        held = tuple(rng.randrange(4) for _ in range(n))
        available = tuple(rng.randint(0, h) for h in held)
        bounds = tuple(rng.randrange(4) for _ in range(n))
        prices = tuple(Fraction(rng.randint(1, 20), 10) for _ in range(n))
        targets = tuple(Fraction(rng.randint(0, 12), 2) for _ in range(n))
        cash = Fraction(rng.randint(0, 200), 10)
        minimum = Fraction(rng.randint(0, 3), 10)
        fixed = Fraction(rng.randint(0, 2), 10)
        rate = Fraction(1, 100)
        request = DiscreteInventoryRequest(
            prices=prices,
            holdings=held,
            target_shares=targets,
            available_sell_shares=available,
            buy_lot_sizes=(1, 1),
            sell_lot_sizes=(1, 1),
            max_buy_lots=bounds,
            cash=cash,
            minimum_fee=minimum,
            fixed_fee=fixed,
            proportional_fee=rate,
        )
        feasible = []
        for trades in product(*(range(-a, b + 1) for a, b in zip(available, bounds))):
            fees = sum(
                (
                    fixed + max(minimum, rate * p * abs(q))
                    for p, q in zip(prices, trades)
                    if q
                ),
                Fraction(),
            )
            purchase = sum((p * max(q, 0) for p, q in zip(prices, trades)), Fraction())
            if purchase + fees > cash:
                continue
            loss = sum(
                ((h + q - t) ** 2 for h, q, t in zip(held, trades, targets)), Fraction()
            )
            terminal = (
                cash + sum((-p * q for p, q in zip(prices, trades)), Fraction()) - fees
            )
            feasible.append((loss, trades, terminal, fees))
        expected = min(feasible)
        result = solve_discrete_inventory(request)
        assert result.status == "optimal_exhaustive"
        assert (
            result.incumbent.objective,
            result.incumbent.trades,
            result.incumbent.projected_cash,
            result.incumbent.fees,
        ) == expected
        assert result.heuristic_gap == result.heuristic.objective - expected[0] >= 0
        largest_gap = max(largest_gap, result.heuristic_gap)
    return {
        "cases": cases,
        "seed": seed,
        "reference": "independent complete feasible-list economics",
        "largest_heuristic_gap": str(largest_gap),
    }


def impact_checks(seed, cases):
    from quant_backtest_core.backtest.impact import LinearImpact

    rng = random.Random(seed)
    maximum_error = 0.0
    for _ in range(cases):
        transient = rng.random() / 100
        permanent = rng.random() / 100
        tau = rng.randint(1, 100)
        quantities = [rng.randint(-100, 100) for _ in range(6)]
        quantities.append(-sum(quantities))
        times = [0]
        for _ in quantities[1:]:
            times.append(times[-1] + rng.randrange(20))
        model = LinearImpact(
            transient=transient, permanent=permanent, decay_seconds=tau
        )
        actual = math.fsum(
            model.execute("A", t, q) * q for t, q in zip(times, quantities)
        )
        kernel = (
            0.5
            * transient
            * math.fsum(
                q * r * math.exp(-abs(t - u) / tau)
                for t, q in zip(times, quantities)
                for u, r in zip(times, quantities)
            )
            + 0.5 * permanent * sum(quantities) ** 2
        )
        assert (
            math.isclose(actual, kernel, rel_tol=1e-11, abs_tol=1e-9)
            and actual >= -1e-9
        )
        maximum_error = max(maximum_error, abs(actual - kernel))
        whole = LinearImpact(
            transient=transient, permanent=permanent, decay_seconds=tau
        )
        split = LinearImpact(
            transient=transient, permanent=permanent, decay_seconds=tau
        )
        q = rng.randint(1, 100)
        cost = whole.execute("A", 0, q) * q
        assert math.isclose(
            cost,
            sum(split.execute("A", 0, q / 5) * (q / 5) for _ in range(5)),
            rel_tol=1e-12,
            abs_tol=1e-9,
        )
        restored = LinearImpact.restore(model.checkpoint())
        assert restored.execute("A", times[-1] + 1, 3) == model.execute(
            "A", times[-1] + 1, 3
        )
        permanent_only = LinearImpact(permanent=permanent)
        permanent_only.execute("A", 0, 10)
        assert permanent_only.offset("A", 1_000_000) == permanent * 10
    return {
        "cases": cases,
        "seed": seed,
        "reference": "symmetric exponential kernel quadratic cost",
        "maximum_absolute_error": maximum_error,
    }


def depth_request(capital="10000"):
    r = json.loads((ROOT / "fixtures/depth.json").read_text())
    r["initial_cash"] = capital
    return r


def event(sequence, dt, asks):
    return {
        "kind": "snapshot",
        "ts_ns": T + dt,
        "available_ns": T + dt,
        "sequence": sequence,
        "bids": [{"price": "9.90", "quantity": "10000000"}],
        "asks": asks,
        "trade_id": None,
        "trade_price": None,
        "trade_quantity": None,
        "aggressor": None,
    }


def command(
    identifier,
    sequence,
    action,
    quantity,
    price="10.10",
    information=T - 1,
    cancel_id=None,
):
    return {
        "id": identifier,
        "event_sequence": sequence,
        "information_ts_ns": information,
        "action": action,
        "quantity": str(quantity),
        "limit_price": price,
        "cancel_id": cancel_id,
    }


def feedback_check(client):
    from quant_backtest_core.planning.discrete_inventory import (
        DiscreteInventoryRequest,
        solve_discrete_inventory,
    )

    r = depth_request()
    r["events"] = [
        event(1, 100, [{"price": "10", "quantity": "4"}]),
        event(2, 200, [{"price": "11", "quantity": "20"}]),
    ]
    r["commands"] = [
        command("first", 1, "target", 10, "10"),
        command("cancel", 2, "cancel", 0, "0", cancel_id="first"),
    ]
    r["end_ns"] = T + 250
    prefix = client.run_depth(r)
    held = prefix["account"]["positions"][0]["quantity"]
    cash = prefix["account"]["cash"]
    assert held == "4" and prefix["account"]["orders"][0]["status"] == "CANCELED"
    plan = solve_discrete_inventory(
        DiscreteInventoryRequest(
            prices=(10,),
            holdings=(int(held),),
            target_shares=(10,),
            available_sell_shares=(int(held),),
            buy_lot_sizes=(1,),
            sell_lot_sizes=(1,),
            max_buy_lots=(10,),
            cash=cash,
            proportional_fee="0.001",
        )
    )
    assert plan.incumbent.trades == (6,)
    full = copy.deepcopy(r)
    full["end_ns"] = T + 1000
    full["events"].append(event(3, 300, [{"price": "10", "quantity": "20"}]))
    full["commands"].append(
        command(
            "next",
            3,
            "target",
            int(held) + plan.incumbent.trades[0],
            "10",
            information=T + 250,
        )
    )
    result = client.run_depth(full)
    assert (
        result["account"]["fills"][: len(prefix["account"]["fills"])]
        == prefix["account"]["fills"]
    )
    assert result["decisions"][-1]["submitted_quantity"] == "6"
    assert result["account"]["positions"][0]["quantity"] == "10"
    return {
        "first_holdings": held,
        "first_cash": cash,
        "second_quantity": result["decisions"][-1]["submitted_quantity"],
        "final_holdings": "10",
        "semantics": "prefix observation -> exact inventory plan -> deterministic full-prefix replay; one native account per run",
        "prefix_input": prefix["request_sha256"],
        "full_input": result["request_sha256"],
    }


def capital_stress(client):
    rows = []
    for capital in ("20000000", "50000000"):
        for depth in (10000, 100000, 1000000):
            for delay in (0, 3000000):
                r = depth_request(capital)
                r["insert_latency_ns"] = delay
                r["end_ns"] = T + 10000000
                r["events"] = [
                    event(
                        1,
                        100,
                        [
                            {"price": "10", "quantity": str(depth)},
                            {"price": "10.1", "quantity": str(depth)},
                        ],
                    ),
                    event(2, 2000000, [{"price": "11", "quantity": str(depth)}]),
                ]
                desired = int(Decimal(capital) / (Decimal("10.1") * Decimal("1.001")))
                r["commands"] = [command("target", 1, "target", desired)]
                result = client.run_depth(r)
                fills = result["account"]["fills"]
                filled = sum(int(f["quantity"]) for f in fills)
                notional = sum(
                    (Decimal(f["price"]) * Decimal(f["quantity"]) for f in fills),
                    Decimal(0),
                )
                expected = 0 if delay else min(desired, 2 * depth)
                assert filled == expected
                rows.append(
                    {
                        "capital": capital,
                        "depth_per_level": depth,
                        "insert_latency_ns": delay,
                        "requested": str(desired),
                        "filled": str(filled),
                        "unfilled": str(desired - filled),
                        "fill_ratio": str(Decimal(filled) / desired),
                        "cash": result["account"]["cash"],
                        "fees": result["account"]["commission"],
                        "execution_price_difference": str(notional - 10 * filled),
                        "opportunity_loss_at_assumed_terminal_11": str(
                            desired - filled
                        ),
                        "input_sha256": result["request_sha256"],
                    }
                )
    return rows


def account_checks(client, seed, cases):
    rng = random.Random(seed)
    total_fills = 0
    for _ in range(cases):
        r = depth_request()
        r["events"] = []
        r["commands"] = []
        r["insert_latency_ns"] = rng.choice([0, 10, 100])
        r["cancel_latency_ns"] = rng.choice([0, 10, 100])
        for i in range(1, 13):
            r["events"].append(
                event(
                    i,
                    100 * i,
                    [
                        {"price": "10", "quantity": str(rng.randint(1, 30))},
                        {"price": "10.1", "quantity": str(rng.randint(1, 30))},
                    ],
                )
            )
            action = rng.choice(["target", "buy", "sell"])
            quantity = rng.randint(1, 100)
            if i % 4 == 0:
                r["commands"].append(
                    command(f"c{i}", i, "cancel", 0, "0", cancel_id=f"c{i - 1}")
                )
            else:
                r["commands"].append(
                    command(
                        f"c{i}",
                        i,
                        action,
                        quantity,
                        "9.90" if action == "sell" else "10.10",
                    )
                )
        result = client.run_depth(r)
        total_fills += len(result["account"]["fills"])
        assert Decimal(result["account"]["cash"]) >= 0
        assert len(result["decisions"]) == 12
        assert all(Decimal(p["quantity"]) >= 0 for p in result["account"]["positions"])
        # SDK independently reconciles every fill prefix and final account, including pending reservations.
    return {
        "cases": cases,
        "seed": seed,
        "decisions": cases * 12,
        "observed_fills": total_fills,
    }


def path_checks(seed):
    import pandas as pd
    from quant_backtest_core.backtest.market_paths import (
        MarketPathSpec,
        fit_market_paths,
        generate_market_paths,
    )
    from quant_backtest_core.backtest.minute import (
        MinuteExecutionConfig,
        simulate_minute_execution,
    )

    train_times = pd.date_range("2026-01-01", periods=8, tz="UTC")
    prices = [10, 10.2, 9.8, 10.1, 10.4, 10.2, 10.5, 10.3]
    training = pd.DataFrame(
        [
            {
                "symbol": "A",
                "time": t,
                "open": p,
                "high": p * 1.02,
                "low": p * 0.98,
                "close": p,
                "volume": 100 + i * 10,
                "amount": p * (100 + i * 10),
            }
            for i, (t, p) in enumerate(zip(train_times, prices))
        ]
    )
    spec = MarketPathSpec(2, seed)
    model = fit_market_paths(training, train_times[-1], spec)
    future = training.iloc[-1:].copy()
    future["time"] = train_times[-1] + pd.Timedelta(days=1)
    future["close"] = -1
    assert (
        fit_market_paths(
            pd.concat([training, future], ignore_index=True), train_times[-1], spec
        )
        == model
    )
    calendar = pd.date_range(
        "2026-01-12 09:29", periods=8, freq="min", tz="Asia/Shanghai"
    )
    ids = tuple(f"path-{i}" for i in range(8))
    paths = generate_market_paths(model, calendar, ids, {"A": 10})
    reverse = generate_market_paths(model, calendar, ids[::-1], {"A": 10})
    prefix = generate_market_paths(model, calendar[:4], ("other", ids[0]), {"A": 10})
    pd.testing.assert_frame_equal(
        paths[ids[0]].iloc[:4].reset_index(drop=True), prefix[ids[0]]
    )
    target = pd.DataFrame(
        [
            {
                "symbol": "A",
                "decision_time": calendar[0],
                "entry_time": calendar[1],
                "weight": 0.5,
            }
        ]
    )
    config = MinuteExecutionConfig(10000, 0.1, 0, 0, lot_size=1)
    results = {}
    for name in ids:
        pd.testing.assert_frame_equal(paths[name], reverse[name])
        bars = paths[name].copy(deep=True)
        bars["interval_start"] = bars.time - pd.Timedelta(seconds=30)
        bars["tradable"] = True
        bars["up_limit"] = bars.high * 2
        bars["down_limit"] = bars.low / 2
        result = simulate_minute_execution(target, bars, config)
        other = simulate_minute_execution(target, bars.copy(deep=True), config)
        pd.testing.assert_frame_equal(result.fills, other.fills)
        pd.testing.assert_frame_equal(result.daily, other.daily)
        results[name] = {
            "final_cash": float(result.daily.iloc[-1].cash),
            "fill_quantity": float(result.fills.quantity.sum())
            if not result.fills.empty
            else 0,
        }
    untouched = paths[ids[1]].copy(deep=True)
    paths[ids[0]].iloc[0, paths[ids[0]].columns.get_loc("close")] = -1
    pd.testing.assert_frame_equal(paths[ids[1]], untouched)
    return {
        "paths": 8,
        "seed": seed,
        "model_hash": model.model_hash,
        "training_future_ignored": True,
        "batch_order_invariant": True,
        "independent_outputs": results,
        "probabilities": "unassigned; generated scenarios have no calibrated occurrence probabilities",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    client = client_for(args.engine)
    report = {
        "schema": "synthetic-assurance.v1",
        "scope": "synthetic correctness and assumed-market stress; real capacity and calibration remain unverified",
        "seed": args.seed,
        "engine_sha256": hashlib.sha256(args.engine.read_bytes()).hexdigest(),
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "native_lots": native_lot_checks(client, args.seed, 32),
        "inventory": inventory_checks(args.seed, 24),
        "impact": impact_checks(args.seed, 24),
        "account": account_checks(client, args.seed, 24),
        "feedback": feedback_check(client),
        "paths": path_checks(args.seed),
        "capital_stress": capital_stress(client),
    }
    report["runtime_source_hashes"] = {
        name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for name, module in sorted(sys.modules.items())
        if name.startswith(("quant_backtest_core", "quant_backtest_engine"))
        and getattr(module, "__file__", None)
        and Path(module.__file__).is_file()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "schema": report["schema"],
                "capital_cases": len(report["capital_stress"]),
            }
        )
    )


if __name__ == "__main__":
    main()
