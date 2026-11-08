"""Public synthetic flow, book, impact, cash and integer-grid cases."""

import json
import subprocess
from decimal import Decimal
import itertools
from method_fixture_common import ROOT, number, scenario, targets, bars, records


def build_market_cases(engine):
    from quant_platform.backtest.impact import LinearImpact
    from quant_platform.backtest.minute import (
        MinuteExecutionConfig,
        simulate_minute_execution,
    )
    from quant_platform.portfolio.discrete_inventory import (
        DiscreteInventoryRequest,
        solve_discrete_inventory,
    )
    from ticknet.simulator.matching import MatchingEngine

    scenes = {}
    request = json.loads((ROOT / "fixtures/roundtrip.json").read_text())
    result = json.loads(
        subprocess.check_output(
            [str(engine), "run", str(ROOT / "fixtures/roundtrip.json")], text=True
        )
    )
    cash, fees, qty = Decimal(request["initial_cash"]), Decimal(0), Decimal(0)
    flow = [
        {
            "clock": str(request["orders"][0]["information_ts_ns"]),
            "cash": number(cash),
            "fees": "0",
            "quantity": "0",
            "price": "10",
            "phase": "forecast",
        }
    ]
    for fill in result["fills"]:
        quantity = Decimal(fill["quantity"]) * (1 if fill["side"] == "buy" else -1)
        cash -= quantity * Decimal(fill["price"]) + Decimal(fill["commission"])
        fees += Decimal(fill["commission"])
        qty += quantity
        flow.append(
            {
                "clock": str(fill["ts_ns"]),
                "cash": number(cash),
                "fees": number(fees),
                "quantity": number(qty),
                "price": fill["price"],
                "phase": fill["side"],
            }
        )
    assert number(cash) == result["cash"]
    scenes["flow"] = {
        "scenarios": [
            scenario(
                "roundtrip",
                flow,
                request,
                ["fixtures/roundtrip.json"],
                owner_name="engine",
                result=result,
                currency="USD",
            )
        ]
    }

    book = MatchingEngine()
    book.apply_order("bid", 1, 99, 100)
    book.apply_order("ask-near", -1, 101, 5)
    book.apply_order("ask-deep", -1, 110, 10)
    trade = book.apply_order("teaching-buy", 1, 110, 20)
    cumulative = 0
    gross = 0
    book_rows = [
        {
            "clock": "0",
            "quantity": "0",
            "remaining": "20",
            "reported": "0",
            "price": "100",
            "gross": "0",
            "phase": "spread",
        }
    ]
    for fill in trade.fills:
        cumulative += fill.volume
        gross += fill.volume * fill.price
        book_rows.append(
            {
                "clock": "1000",
                "quantity": str(cumulative),
                "remaining": str(20 - cumulative),
                "reported": "0",
                "price": str(fill.price),
                "gross": str(gross),
                "phase": "fill",
            }
        )
    # Explicit presentation/report-delay assumption, not a matching-engine latency model.
    book_rows.append(
        dict(book_rows[-1], clock="1600", reported=str(cumulative), phase="report")
    )
    scenes["book"] = {
        "scenarios": [
            scenario(
                "depth",
                book_rows,
                {
                    "bid": [99, 100],
                    "asks": [[101, 5], [110, 10]],
                    "order": [110, 20],
                    "report_delay_ms": 600,
                },
                ["packages/microstructure/src/ticknet/simulator/matching.py"],
                report_scope="illustrative 600 ms delivery schedule; actual delayed accounting is scene risk",
            )
        ]
    }

    impact_scenarios = []
    for ident, quantity, spacing, permanent in [
        ("small", 100, 60, 0),
        ("large", 200, 120, 0),
        ("nondecaying", 100, 60, 0.001),
        ("close", 100, 10, 0),
    ]:
        config = {"transient": 0.002, "permanent": permanent, "decay_seconds": 60}
        model = LinearImpact(**config)
        rows = []
        for clock, q in [
            (0, quantity),
            (spacing, 0),
            (spacing, quantity),
            (spacing + 180, 0),
        ]:
            offset = model.execute("A", clock, q) if q else model.offset("A", clock)
            state = model.checkpoint()["states"]["A"]
            rows.append(
                {
                    "clock": str(clock),
                    "quantity": str(q),
                    "unaffected": "10",
                    "offset": number(offset),
                    "transient": number(state["transient"]),
                    "permanent": number(state["permanent"]),
                    "price": number(10 + offset),
                    "phase": "fill" if q else "decay",
                }
            )
        impact_scenarios.append(
            scenario(
                ident,
                rows,
                dict(config, quantity=quantity, spacing=spacing),
                ["packages/platform/src/quant_platform/backtest/impact.py"],
            )
        )
    scenes["impact"] = {"scenarios": impact_scenarios}

    shared_inputs = {
        "initial_cash": 12000,
        "participation": 0.1,
        "target": 5 / 6,
        "minimum_fee": 1,
        "permanent": 0.002,
    }
    t = targets(weights=(5 / 6,))
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32"))
    impact = LinearImpact(permanent=0.002)
    shared = simulate_minute_execution(
        t,
        b,
        MinuteExecutionConfig(12000, 0.1, 0, 0, commission_minimum_cny=1),
        impact_model=impact,
    )
    f = shared.fills.iloc[0]
    cost_rows = [
        {
            "clock": str(t.decision_time.iloc[0].value),
            "cash": "12000",
            "quantity": "0",
            "gross": "0",
            "fees": "0",
            "impact_cost": "0",
            "phase": "reserve",
        },
        {
            "clock": str(f.time.value),
            "cash": number(shared.daily.iloc[-1].cash),
            "quantity": number(f.quantity),
            "gross": number(f.gross_amount),
            "fees": number(f.transaction_cost),
            "impact_cost": number((f.price - 10) * f.quantity),
            "price": number(f.price),
            "phase": "cash",
        },
    ]
    # Avoid binary subtraction artifacts: decomposition uses exact owner price strings.
    cost_rows[-1]["impact_cost"] = number(
        (Decimal(str(f.price)) - Decimal(10)) * Decimal(str(f.quantity))
    )
    scenes["cost"] = {
        "scenarios": [
            scenario(
                "once",
                cost_rows,
                shared_inputs,
                ["packages/platform/src/quant_platform/backtest/minute.py"],
                fills=records(shared.fills),
            )
        ]
    }

    lot_scenarios = []
    for ident, fee, target in [
        ("no-minimum", 0, "1.6"),
        ("minimum", 1, "1.6"),
        ("grid", 1, "1.5"),
    ]:
        config = {
            "prices": (6, 4),
            "holdings": (0, 0),
            "target_shares": (target, target),
            "available_sell_shares": (0, 0),
            "buy_lot_sizes": (1, 1),
            "sell_lot_sizes": (1, 1),
            "max_buy_lots": (3, 3),
            "cash": 14,
            "minimum_fee": fee,
        }
        solved = solve_discrete_inventory(DiscreteInventoryRequest(**config))
        rows = []
        for phase, plan in [
            ("heuristic", solved.heuristic),
            ("bounded", solved.incumbent),
        ]:
            rows.append(
                {
                    "phase": phase,
                    "clock": "0",
                    "shares": ",".join(map(str, plan.holdings)),
                    "cash": number(plan.projected_cash),
                    "fees": number(plan.fees),
                    "error": number(plan.objective),
                    "quantity": str(sum(plan.holdings)),
                }
            )
        grid = []
        for state in itertools.product(range(4), repeat=2):
            oracle = solve_discrete_inventory(
                DiscreteInventoryRequest(**(config | {"target_shares": state}))
            )
            grid.append(
                {
                    "shares": ",".join(map(str, state)),
                    "feasible": oracle.incumbent.holdings == state,
                    "cash": number(oracle.incumbent.projected_cash)
                    if oracle.incumbent.holdings == state
                    else None,
                }
            )
        lot_scenarios.append(
            scenario(
                ident,
                rows,
                config,
                [
                    "packages/platform/src/quant_platform/portfolio/discrete_inventory.py"
                ],
                grid=grid,
                status=solved.status,
                domain_states=solved.domain_states,
            )
        )
    scenes["lots"] = {"scenarios": lot_scenarios}

    return scenes, (shared_inputs, shared, cost_rows)
