"""Public synthetic financial-action case; all transitions belong to Platform."""


def build_action_case(targets, bars, records, scenario, number, digest, policy_type):
    import json
    import pandas as pd
    from quant_platform.backtest.minute import (
        CapitalFlow,
        CorporateAction,
        MinuteExecutionConfig,
        ValuationEvent,
    )
    from quant_platform.backtest.minute_session import MinuteSession
    from quant_platform.backtest.quantity_locks import QuantityLock

    t = targets(("2026-01-05 09:30", "2026-01-06 09:30", "2026-01-07 09:30"), (1, 0, 0))
    b = pd.concat(
        [
            bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:33")),
            bars(("2026-01-06 09:29", "2026-01-06 09:32"), price=4.5),
            bars(("2026-01-07 09:29", "2026-01-07 09:32"), price=4.5),
        ],
        ignore_index=True,
    )
    cfg = MinuteExecutionConfig(10000, 0.1, 0, 0)
    action = CorporateAction(
        "distribution",
        "A",
        "2026-01-04",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
        stock_per_share=1,
        stock_tradable_date="2026-01-07",
    )
    start = int(pd.Timestamp("2026-01-06", tz="Asia/Shanghai").value)
    end = int(pd.Timestamp("2026-01-07 09:30", tz="Asia/Shanghai").value)
    lock = QuantityLock(start, start, end, ("A",), "synthetic")
    baseline = MinuteSession(
        t,
        b,
        cfg,
        policy=policy_type(),
        corporate_actions=(action,),
        quantity_locks=(lock,),
    ).run()
    states = []
    for index, row in enumerate(baseline.daily.itertuples()):
        price = 10 if index == 0 else 4.5
        states.append(
            {
                "clock": str(row.date),
                "phase": ["buy", "ex", "release"][index],
                "cash": number(row.cash),
                "quantity": number(row.positions_value / price),
                "cash_right": number(row.cash_receivable),
                "stock_right": number(row.stock_receivable_value / price),
                "wealth": number(row.nav),
                "capital_flow": "0",
            }
        )
    b.loc[b.time.dt.day >= 7, "tradable"] = False
    valuation = ValuationEvent(
        "terminal",
        "A",
        "2026-01-07 09:29+08:00",
        "2026-01-07 09:28+08:00",
        3,
        "declared",
        "synthetic",
    )
    flow = CapitalFlow(
        "deposit", "2026-01-07 09:28+08:00", "2026-01-07 09:29+08:00", 1000, "synthetic"
    )

    def make():
        return MinuteSession(
            t,
            b,
            cfg,
            policy=policy_type(),
            report_delay_seconds=600,
            corporate_actions=(action,),
            valuation_events=(valuation,),
            capital_flows=(flow,),
            quantity_locks=(lock,),
        )

    full = make()
    result = full.run()
    names = [
        "daily",
        "fills",
        "orders",
        "holdings",
        "valuation_ledger",
        "capital_flow_ledger",
    ]
    expected = {name: records(getattr(result, name)) for name in names}
    for boundary in range(len(full.simulation.times) + 1):
        session = make()
        for _ in range(boundary):
            session.step()
        checkpoint = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
        policy = policy_type()
        policy.rows = checkpoint["policy"]["rows"]
        policy.hold = checkpoint["policy"]["hold"]
        restored = MinuteSession.restore(t, b, cfg, checkpoint, policy=policy).run()
        if expected != {name: records(getattr(restored, name)) for name in names}:
            raise AssertionError("financial-action checkpoint parity failed")
    states.append(
        {
            "clock": "2026-01-07T09:29:00+08:00",
            "phase": "capital",
            "cash": number(result.daily.iloc[-1].cash),
            "quantity": number(result.holdings.iloc[-1].quantity),
            "cash_right": "0",
            "stock_right": "0",
            "wealth": number(result.daily.iloc[-1].nav),
            "wealth_before_flow": number(result.capital_flow_ledger.iloc[0].nav_before),
            "capital_flow": "1000",
        }
    )
    return scenario(
        "actions",
        states,
        {
            "targets": records(t),
            "bars": records(b),
            "initial_cash": 10000,
            "distribution": action,
            "lock": lock,
            "valuation": valuation,
            "capital_flow": flow,
        },
        ["packages/platform/src/quant_platform/backtest/minute_session.py"],
        uninterrupted_sha256=digest(expected),
        recovered_sha256=digest(expected),
        capital_flow_ledger=records(result.capital_flow_ledger),
        valuation_ledger=records(result.valuation_ledger),
    )
