"""Independent account paths, public teaching search and financial recovery cases."""

import itertools
import json
import pandas as pd
from method_fixture_common import (
    number,
    wire,
    digest,
    scenario,
    targets,
    bars,
    records,
    Policy,
)


def build_session_cases(shared_case):
    from quant_platform.backtest.impact import LinearImpact
    from quant_platform.backtest.minute import (
        MinuteExecutionConfig,
        simulate_minute_execution,
    )
    from quant_platform.backtest.minute_session import MinuteSession
    from quant_platform.backtest.quantity_locks import QuantityLock
    from quant_platform.portfolio.sleeve_allocation import (
        SleeveDemand,
        net_sleeve_demands,
        allocate_external_fills,
    )
    from quant_platform.analytics.execution_integrity import exit_wealth
    from quant_platform.scenarios import build_scenario

    shared_inputs, shared, cost_rows = shared_case
    f = shared.fills.iloc[0]
    scenes = {}
    path_scenarios = []
    t = targets(("2026-01-05 09:30", "2026-01-05 09:34"), (1, 1))
    for ident, participation, last_price, hold in [
        ("thin", 0.1, 10, False),
        ("deep", 0.5, 10, False),
        ("market-up", 0.1, 10.5, False),
        ("feedback", 0.1, 10, True),
    ]:
        b = bars()
        b.loc[2, ["open", "high", "low", "close"]] = last_price
        b.loc[2, "amount"] = last_price * 1000
        policy = Policy(hold)
        delivered = simulate_minute_execution(
            t,
            b,
            MinuteExecutionConfig(10000, participation, 0, 0),
            decision_policy=policy,
        )
        rows = [dict(row, phase="decision") for row in policy.rows]
        end = delivered.daily.iloc[-1]
        rows.append(
            {
                "clock": str(b.time.iloc[-1].value),
                "cash": number(end.cash),
                "quantity": number(delivered.fills.quantity.sum()),
                "price": str(last_price),
                "next_target": policy.rows[-1]["next_target"],
                "phase": "account",
            }
        )
        path_scenarios.append(
            scenario(
                ident,
                rows,
                {
                    "targets": records(t),
                    "bars": records(b),
                    "participation": participation,
                    "hold_actual": hold,
                },
                ["packages/platform/src/quant_platform/backtest/minute.py"],
                forecast_sha256=digest(records(t)),
                market_sha256=digest(records(b)),
                fills=records(delivered.fills),
                orders=records(delivered.orders),
            )
        )
    scenes["paths"] = {"scenarios": path_scenarios}

    null = build_scenario("null_signal", seed=0)
    returns = null.frames["signals"]["return"].tolist()
    trial_rows = []
    # Six predeclared balanced portfolios; no fitted signal, no filtering of failures.
    for i, chosen in enumerate(itertools.combinations(range(4), 2)):
        weights = [0.5 if j in chosen else 0 for j in range(4)]
        score = sum(w * r for w, r in zip(weights, returns, strict=True))
        trial_rows.append(
            {
                "clock": str(i),
                "trial": str(i + 1),
                "score": number(score),
                "selected": False,
                "shares": ",".join(null.frames["signals"].symbol.iloc[list(chosen)]),
                "phase": "trial",
            }
        )
    best = max(range(len(trial_rows)), key=lambda i: float(trial_rows[i]["score"]))
    trial_rows[best]["selected"] = True
    scenes["selection"] = {
        "scenarios": [
            scenario(
                "null-search",
                trial_rows,
                {
                    "seed": 0,
                    "rule": "all six 2-of-4 equal-weight subsets; maximum same-sample return; first tie wins",
                    "signals": records(null.frames["signals"]),
                },
                [
                    "packages/platform/src/quant_platform/scenarios.py",
                    "project_tools/method_session_cases.py",
                ],
                truth=null.truth,
                scope="finite teaching enumeration only; no PBO/CSCV or real out-of-sample claim",
            )
        ]
    }

    # Real session checkpoints, restored at every possible unfinished event boundary.
    t = targets(("2026-01-05 09:30", "2026-01-05 09:34"), (1, 1))
    b = bars()
    cfg = MinuteExecutionConfig(10000, 0.1, 0, 0)

    def make():
        return MinuteSession(
            t,
            b,
            cfg,
            policy=Policy(),
            report_delay_seconds=600,
            impact=LinearImpact(transient=0.002),
        )

    full = make()
    expected = full.run()
    expected_wire = {
        name: records(getattr(expected, name))
        for name in ["daily", "orders", "fills", "holdings"]
    }
    checks = []
    for boundary in range(len(full.simulation.times) + 1):
        part = make()
        for _ in range(boundary):
            part.step()
        checkpoint = json.loads(json.dumps(part.checkpoint(), allow_nan=False))
        policy = Policy()
        policy.rows = checkpoint["policy"]["rows"]
        policy.hold = checkpoint["policy"]["hold"]
        restored = MinuteSession.restore(t, b, cfg, checkpoint, policy=policy)
        recovered = restored.run()
        recovered_wire = {
            name: records(getattr(recovered, name)) for name in expected_wire
        }
        if expected_wire != recovered_wire:
            raise AssertionError("restored owner financial tables differ")
        checks.append(
            {
                "clock": str(boundary),
                "quantity": number(recovered.fills.quantity.sum()),
                "cash": number(recovered.daily.iloc[-1].cash),
                "phase": "restore",
                "report_pending": bool(part.queue),
            }
        )
    recovery = scenario(
        "recovery",
        checks,
        {
            "targets": records(t),
            "bars": records(b),
            "delay_seconds": 600,
            "initial_cash": 10000,
            "impact_transient": 0.002,
        },
        ["packages/platform/src/quant_platform/backtest/minute_session.py"],
        uninterrupted_sha256=digest(expected_wire),
        recovered_sha256=digest(recovered_wire),
        decision_reports=full.policy.rows,
    )
    demands = [
        SleeveDemand(
            s,
            "A",
            500,
            "6000",
            0,
            0,
            0,
            max_buy_price="11",
            fee_budget="1",
            lot_size=100,
        )
        for s in ["a", "b"]
    ]
    plan = net_sleeve_demands(demands, reference_prices={"A": "10"})
    fill = {
        "fill_id": "synthetic-owner-row-0",
        "ts_ns": int(f.time.value),
        "symbol": "A",
        "side": "buy",
        "quantity": int(f.quantity),
        "price": str(f.price),
        "gross_amount": str(f.gross_amount),
        "fee": str(f.transaction_cost),
    }
    allocated = allocate_external_fills(plan, [fill, fill])
    sharing = scenario(
        "shared",
        cost_rows,
        shared_inputs | {"demands": wire(demands)},
        ["packages/platform/src/quant_platform/portfolio/sleeve_allocation.py"],
        allocation=wire(allocated),
        external_orders=wire(plan.external_orders),
    )
    t = targets(
        ("2026-01-05 09:30", "2026-01-06 09:30", "2026-01-07 09:30"), (0.5, 0, 0)
    )
    b = bars(
        tuple(f"2026-01-{d:02} {m}" for d in (5, 6, 7) for m in ("09:29", "09:32"))
    )
    b.loc[b.time.dt.day == 7, "volume"] = 200
    b["amount"] = b.volume * 10
    start = int(pd.Timestamp("2026-01-06 09:00", tz="Asia/Shanghai").value)
    end = int(pd.Timestamp("2026-01-06 15:00", tz="Asia/Shanghai").value)
    lock = QuantityLock(start, start, end, ("A",), "synthetic-notice")
    exit_result = MinuteSession(
        t,
        b,
        MinuteExecutionConfig(10000, 0.5, 0, 0),
        policy=Policy(),
        quantity_locks=(lock,),
    ).run()
    clock = int(b.time.iloc[-1].value)
    final_cash = exit_result.daily.iloc[-1].cash
    quantities = {r.symbol: int(r.quantity) for r in exit_result.holdings.itertuples()}
    if not quantities:
        quantities = {"A": int(exit_result.holdings.iloc[-1].quantity)}
    wealth = exit_wealth(
        str(final_cash),
        quantities,
        {"A": {"price": "10", "ts_ns": clock}},
        as_of_ns=clock,
        max_mark_age_ns=0,
    )
    exits = []
    for i, row in enumerate(exit_result.daily.itertuples()):
        exits.append(
            {
                "clock": str(row.date),
                "cash": number(row.cash),
                "quantity": number(row.positions_value / 10),
                "wealth": number(row.nav),
                "phase": ["buy", "locked", "residual"][i],
                "cash_realized_wealth": None,
            }
        )
    exits[-1]["wealth"] = number(wealth["marked_wealth"])
    exits[-1]["cash_realized_wealth"] = wealth["cash_realized_wealth"]
    residual = scenario(
        "residual",
        exits,
        {
            "targets": records(t),
            "bars": records(b),
            "lock": wire(lock),
            "initial_cash": 10000,
        },
        [
            "packages/platform/src/quant_platform/analytics/execution_integrity.py",
            "packages/platform/src/quant_platform/backtest/minute_session.py",
        ],
        exit_wealth=wire(wealth),
        fills=records(exit_result.fills),
    )
    from method_action_case import build_action_case

    actions = build_action_case(
        targets, bars, records, scenario, number, digest, Policy
    )
    from method_risk_case import build_risk_cases

    scenes["risk"] = {
        "scenarios": [
            recovery,
            sharing,
            residual,
            actions,
            *build_risk_cases(records, scenario, number),
        ]
    }
    return scenes
