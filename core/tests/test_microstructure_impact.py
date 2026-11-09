"""RED: 冲击成本估计接口。

把候选执行单放入合成回放会话，核对成交证据与中间价变化。
"""

from __future__ import annotations

import pytest

from quant_backtest_core.microstructure.impact import ExecutionSchedule, ImpactEstimator
from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure.replay import InterventionOrder, ReplaySession


def test_impact_estimator_reports_slippage():
    engine = MatchingEngine()
    session = ReplaySession(engine=engine, initial_bid=(1000, 500), initial_ask=(1001, 300))

    # 买 1 亿元等价：这里用股数近似，分 4 个子单
    schedule = ExecutionSchedule(
        side=1,
        total_volume=2000,
        n_child=4,
        start_time_ms=1000,
        end_time_ms=5000,
    )
    estimator = ImpactEstimator(session=session)
    result = estimator.estimate(schedule)

    assert result.mid_before == 1000.5  # 买一卖一中间价 (1000+1001)/2
    assert result.mid_after is not None
    assert result.slippage_bps >= 0  # 买入冲击非负
    assert result.filled_volume == 300
    assert result.unfilled_volume == 1700


def test_larger_order_has_higher_impact():
    def run(total: int) -> float:
        engine = MatchingEngine()
        session = ReplaySession(engine=engine, initial_bid=(1000, 500), initial_ask=(1001, 300))
        sched = ExecutionSchedule(
            side=1, total_volume=total, n_child=4, start_time_ms=1000, end_time_ms=5000
        )
        return ImpactEstimator(session=session).estimate(sched).slippage_bps

    small = run(500)
    large = run(2000)
    assert large >= small  # 买入量越大，冲击不小于小单


def test_partial_fill_uses_execution_evidence():
    session = ReplaySession(MatchingEngine(), (1000, 500), (1001, 30))
    result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 100, n_child=3))
    assert result.filled_volume == 30
    assert result.unfilled_volume == 70
    assert result.execution_vwap == 1001
    assert sum(fill.volume for fill in result.fills) == 30


def test_zero_fill_has_no_execution_price():
    session = ReplaySession(MatchingEngine(), (1000, 500), (1001, 0))
    result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 100))
    assert result.filled_volume == 0
    assert result.unfilled_volume == 100
    assert result.execution_vwap is None
    assert result.execution_slippage_bps is None
    assert result.fills == ()


def test_fill_vwap_includes_multiple_prices_and_excludes_background():
    session = ReplaySession(MatchingEngine(), (90, 100), (110, 10))
    session.add_background(100, -1, 101, 5, "cheaper")
    session.add_background(200, 1, 90, 1, "unrelated-bid")
    session.add_background(300, -1, 90, 1, "unrelated-sell")
    result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 15))
    assert result.filled_volume == 15
    assert result.execution_vwap == (101 * 5 + 110 * 10) / 15
    assert [(f.price, f.volume) for f in result.fills] == [(101, 5), (110, 10)]
    assert result.execution_slippage_bps == (result.execution_vwap / 100 - 1) * 10000


def test_sell_fill_evidence_and_direction():
    session = ReplaySession(MatchingEngine(), (90, 10), (110, 100))
    session.add_background(100, 1, 99, 5, "better-bid")
    result = ImpactEstimator(session).estimate(ExecutionSchedule(-1, 20, n_child=2))
    assert result.filled_volume == 15
    assert result.unfilled_volume == 5
    assert result.execution_vwap == (99 * 5 + 90 * 10) / 15
    assert result.execution_slippage_bps > 0


def test_passive_child_fills_are_attributed_once_across_runs():
    session = ReplaySession(MatchingEngine(), (1000, 50), (1001, 10))
    session.add_background(2000, -1, 1001, 5, "later-sell")
    estimator = ImpactEstimator(session)
    first = estimator.estimate(ExecutionSchedule(1, 30, n_child=2))
    assert first.filled_volume == 15
    assert len({f.buy_id for f in first.fills}) == 1
    ticks = len(session.ticks)
    session.run()
    assert len(session.ticks) == ticks
    second = estimator.estimate(ExecutionSchedule(1, 10, start_time_ms=6000))
    assert second.filled_volume == 0
    assert second.fills == ()


def test_child_ids_do_not_collide_with_existing_session_orders():
    from quant_backtest_core.microstructure.replay import InterventionOrder

    session = ReplaySession(MatchingEngine(), (100, 50), (101, 10))
    session.add_intervention(InterventionOrder(500, 1, 101, 1, "IMPACT0"))
    session.add_background(500, 1, 101, 1, "IMPACT1")
    result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 20, n_child=2))
    assert result.filled_volume == 8
    assert all(f.buy_id not in {"IMPACT0", "IMPACT1"} for f in result.fills)


def test_rust_backend_rejects_missing_fill_capability_before_mutation():
    import pytest

    session = ReplaySession(MatchingEngine(), (100, 50), (101, 10))
    session.engine.backend = "rust"
    with pytest.raises(NotImplementedError, match="per-fill execution evidence"):
        ImpactEstimator(session).estimate(ExecutionSchedule(1, 20))
    assert len(session.ticks) == 1
    assert session.engine.lob.best_ask() == (101, 10)


def test_reserved_child_id_excludes_queued_history_and_live_book():
    session = ReplaySession(MatchingEngine(), (100, 50), (101, 10))
    session.add_background(1, 1, 101, 1, "candidate")
    session.run()
    session.engine.apply_order("candidate_1", 1, 99, 1)
    assert session.reserve_order_id("candidate") == "candidate_2"
    assert session.reserve_order_id("candidate") == "candidate_3"


def test_child_fill_evidence_is_deterministic_and_reconciles_remainders():
    def run():
        session = ReplaySession(MatchingEngine(), (100, 50), (101, 20))
        return ImpactEstimator(session).estimate(ExecutionSchedule(1, 11, n_child=3)).fills

    fills = run()
    assert fills == run()
    assert [f.volume for f in fills] == [3, 3, 5]
    assert len({f.buy_id for f in fills}) == 3


def test_impact_past_schedule_rejects_before_reserving_child_ids():
    replay = ReplaySession(MatchingEngine(), (100, 50), (101, 50))
    replay.add_background(10000, 1, 101, 5)
    replay.run()
    with pytest.raises(ValueError, match="processed replay time"):
        ImpactEstimator(replay).estimate(ExecutionSchedule(1, 10, start_time_ms=1000))
    replay.run()
    assert replay.engine.lob.best_ask() == (101, 45)
    assert replay.reserve_order_id("IMPACT0") == "IMPACT0"


def test_impact_checks_existing_mutated_queue_before_reserving_child_ids():
    replay = ReplaySession(MatchingEngine(), (100, 50), (101, 50))
    replay.add_background(10, 1, 101, 5)
    replay.run()
    order = InterventionOrder(11, 1, 101, 7, "existing")
    replay.add_intervention(order)
    order.time_ms = 9
    with pytest.raises(ValueError, match="processed replay time"):
        ImpactEstimator(replay).estimate(ExecutionSchedule(1, 10, start_time_ms=20))
    assert replay.engine.lob.best_ask() == (101, 45)
    assert replay.reserve_order_id("IMPACT0") == "IMPACT0"


def test_empty_book_midpoint_sentinels_are_not_measured_zero_impact():
    from quant_backtest_core.microstructure.impact import _mid

    session = ReplaySession(MatchingEngine(), (100, 0), (101, 0))
    assert _mid(session) == 0.0
    result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 0))
    assert result.mid_before == result.mid_after == result.slippage_bps == 0.0
    assert result.filled_volume == result.unfilled_volume == 0
    assert result.execution_vwap is result.execution_slippage_bps is None
    assert result.fills == ()
    # An unfilled child rests at the legacy empty-book fallback price.
    result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 5))
    assert result.mid_before == result.slippage_bps == 0.0
    assert result.mid_after == 1.0
    assert result.filled_volume == 0 and result.unfilled_volume == 5
    assert result.execution_vwap is result.execution_slippage_bps is None
    assert result.fills == ()

    # Consuming the only populated side returns the raw empty midpoint sentinel.
    # Preserve its large signed displacement; it is not a measured market impact.
    for side, bid, ask, before, raw_slippage in (
        (1, (100, 0), (101, 5), 101.0, -10000.0),
        (-1, (100, 5), (101, 0), 100.0, 10000.0),
    ):
        empty_after = ReplaySession(MatchingEngine(), bid, ask)
        receipt = ImpactEstimator(empty_after).estimate(ExecutionSchedule(side, 5))
        assert receipt.mid_before == before
        assert receipt.mid_after == _mid(empty_after) == 0.0
        assert receipt.slippage_bps == raw_slippage
        assert receipt.execution_vwap == before
        assert receipt.execution_slippage_bps == 0.0
        assert receipt.filled_volume == 5 and receipt.unfilled_volume == 0
