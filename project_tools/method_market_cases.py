"""Public synthetic flow, book, impact, cash and integer-grid cases."""

import json
import subprocess
from decimal import Decimal
import itertools
from method_fixture_common import ROOT, number, scenario, targets, bars, records
from method_owner_calls import define_call, execute_call


def build_market_cases(engine):
    from quant_backtest_core.backtest.impact import LinearImpact
    from quant_backtest_core.backtest.minute import (
        MinuteExecutionConfig,
    )
    from quant_backtest_core.planning.discrete_inventory import (
        DiscreteInventoryRequest,
    )

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

    book_inputs = {
        "runs": {"matcher": define_call("matching")},
        "orders": [
            ("bid", 1, 99, 100),
            ("ask-near", -1, 101, 5),
            ("ask-deep", -1, 110, 10),
            ("teaching-buy", 1, 110, 20),
        ],
        "initial_clock_ms": 0,
        "match_clock_ms": 1000,
        "report_delay_ms": 600,
        "initial_mid": 100,
    }
    book = execute_call(book_inputs["runs"]["matcher"])
    for order in book_inputs["orders"]:
        trade = book.apply_order(*order)
    requested = book_inputs["orders"][-1][-1]
    cumulative = 0
    gross = 0
    book_rows = [
        {
            "clock": "0",
            "quantity": "0",
            "remaining": str(requested),
            "reported": "0",
            "price": str(book_inputs["initial_mid"]),
            "gross": "0",
            "phase": "spread",
        }
    ]
    for fill in trade.fills:
        cumulative += fill.volume
        gross += fill.volume * fill.price
        book_rows.append(
            {
                "clock": str(book_inputs["match_clock_ms"]),
                "quantity": str(cumulative),
                "remaining": str(requested - cumulative),
                "reported": "0",
                "price": str(fill.price),
                "gross": str(gross),
                "phase": "fill",
            }
        )
    # Explicit presentation/report-delay assumption, not a matching-engine latency model.
    book_rows.append(
        dict(
            book_rows[-1],
            clock=str(book_inputs["match_clock_ms"] + book_inputs["report_delay_ms"]),
            reported=str(cumulative),
            phase="report",
        )
    )
    scenes["book"] = {
        "scenarios": [
            scenario(
                "depth",
                book_rows,
                book_inputs,
                ["core/src/quant_backtest_core/microstructure/matching.py"],
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
        impact_inputs = {
            "runs": {"model": define_call("impact", **config)},
            "symbol": "A",
            "unaffected_price": 10,
            "events": [
                (0, quantity),
                (spacing, 0),
                (spacing, quantity),
                (spacing + 180, 0),
            ],
        }
        model = execute_call(impact_inputs["runs"]["model"])
        rows = []
        for clock, q in impact_inputs["events"]:
            symbol = impact_inputs["symbol"]
            offset = (
                model.execute(symbol, clock, q) if q else model.offset(symbol, clock)
            )
            state = model.checkpoint()["states"][symbol]
            rows.append(
                {
                    "clock": str(clock),
                    "quantity": str(q),
                    "unaffected": number(impact_inputs["unaffected_price"]),
                    "offset": number(offset),
                    "transient": number(state["transient"]),
                    "permanent": number(state["permanent"]),
                    "price": number(impact_inputs["unaffected_price"] + offset),
                    "phase": "fill" if q else "decay",
                }
            )
        impact_scenarios.append(
            scenario(
                ident,
                rows,
                impact_inputs,
                ["core/src/quant_backtest_core/backtest/impact.py"],
            )
        )
    scenes["impact"] = {"scenarios": impact_scenarios}

    t = targets(weights=(5 / 6,))
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32"))
    execution = define_call(
        "minute",
        t,
        b,
        MinuteExecutionConfig(12000, 0.1, 0, 0, commission_minimum_cny=1),
        impact_model=LinearImpact(permanent=0.002),
    )
    shared_inputs = {"runs": {"execution": execution}}
    shared = execute_call(execution)
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
                ["core/src/quant_backtest_core/backtest/minute.py"],
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
        planning = define_call("discrete", DiscreteInventoryRequest(**config))
        planning_runs = {"planning": planning}
        solved = execute_call(planning)
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
            request = define_call(
                "discrete",
                DiscreteInventoryRequest(**(config | {"target_shares": state})),
            )
            planning_runs[f"grid-{state[0]}-{state[1]}"] = request
            oracle = execute_call(request)
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
                {"runs": planning_runs},
                [
                    "core/src/quant_backtest_core/planning/discrete_inventory.py"
                ],
                grid=grid,
                status=solved.status,
                domain_states=solved.domain_states,
            )
        )
    scenes["lots"] = {"scenarios": lot_scenarios}

    return scenes, (shared_inputs, shared, cost_rows)
