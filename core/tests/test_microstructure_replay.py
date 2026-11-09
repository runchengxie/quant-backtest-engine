"""RED: 生成式回放闭环。

prefix（初始盘口）+ 背景订单流（Transformer 生成）+ 外部干预订单
→ 经撮合引擎回放 → 合成市场轨迹。
"""

from __future__ import annotations

from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure.replay import InterventionOrder, ReplaySession


def test_replay_session_initializes_from_snapshot():
    engine = MatchingEngine()
    ReplaySession(engine=engine, initial_bid=(1000, 500), initial_ask=(1001, 300))
    # 初始盘口应已注入撮合引擎
    assert engine.lob.best_bid() == (1000, 500)
    assert engine.lob.best_ask() == (1001, 300)


def test_intervention_order_injected_into_stream():
    engine = MatchingEngine()
    session = ReplaySession(engine=engine, initial_bid=(1000, 500), initial_ask=(1001, 300))
    # 外部买入大单，应吃掉卖一 300 股，剩余 200 挂在 1001
    session.add_intervention(
        InterventionOrder(
            time_ms=1000,
            side=1,
            price=1001,
            volume=500,
        )
    )
    session.run()
    # 卖一被吃完，买一 1000 剩 500，买一 1001 挂 200
    best_ask = engine.lob.best_ask()
    assert best_ask is None or best_ask[0] > 1001
    assert engine.lob.best_bid() == (1001, 200)


def test_background_order_stream_consumed():
    engine = MatchingEngine()
    session = ReplaySession(engine=engine, initial_bid=(1000, 500), initial_ask=(1001, 300))
    # 注入一笔背景卖单（模型生成），价格 1000，应部分吃掉买一
    session.add_background(time_ms=500, side=-1, price=1000, volume=200)
    session.run()
    assert engine.lob.best_bid() == (1000, 300)


def test_repeated_run_does_not_reapply_orders_and_keeps_fill_history():
    session = ReplaySession(MatchingEngine(), (100, 50), (101, 50))
    session.add_background(1, 1, 101, 10, "first")
    session.run()
    fills = tuple(session.fills)
    session.run()
    assert session.engine.lob.best_ask() == (101, 40)
    assert tuple(session.fills) == fills
    session.add_background(2, 1, 101, 5, "second")
    session.run()
    assert session.engine.lob.best_ask() == (101, 35)
    assert [(f.buy_id, f.volume) for f in session.fills] == [("first", 10), ("second", 5)]


def test_fill_evidence_uses_time_order_with_interventions_first_on_ties():
    session = ReplaySession(MatchingEngine(), (100, 50), (101, 50))
    session.add_background(2, 1, 101, 2, "bg-later")
    session.add_background(1, 1, 101, 3, "bg-tie")
    session.add_intervention(InterventionOrder(1, 1, 101, 4, "iv-tie"))
    session.run()
    assert [(f.time_ms, f.buy_id, f.volume) for f in session.fills] == [
        (1, "iv-tie", 4),
        (1, "bg-tie", 3),
        (2, "bg-later", 2),
    ]


def test_automatic_background_ids_do_not_reuse_explicit_or_historical_ids():
    session = ReplaySession(MatchingEngine(), (100, 50), (101, 50))
    session.add_background(1, 1, 101, 1, "BG1")
    session.add_background(2, 1, 101, 1)
    session.run()
    assert len({f.buy_id for f in session.fills}) == 2
    session.add_background(3, 1, 101, 1)
    session.run()
    assert len({f.buy_id for f in session.fills}) == 3
