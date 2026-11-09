"""冲击成本估计。

把候选执行单（ExecutionSchedule）注入回放会话作为干预订单，
对比执行前后中间价，估计 slippage（基点）与成交量。
"""

from __future__ import annotations

from dataclasses import dataclass

from .replay import InterventionOrder, ReplayFill, ReplaySession


@dataclass
class ExecutionSchedule:
    side: int  # 1 买, -1 卖
    total_volume: int
    n_child: int = 1
    start_time_ms: int = 1000
    end_time_ms: int = 5000


@dataclass
class ImpactResult:
    mid_before: float
    mid_after: float
    slippage_bps: float
    filled_volume: int
    unfilled_volume: int = 0
    execution_vwap: float | None = None
    execution_slippage_bps: float | None = None
    fills: tuple[ReplayFill, ...] = ()


def _mid(session: ReplaySession) -> float:
    bid = session.engine.lob.best_bid()
    ask = session.engine.lob.best_ask()
    if bid is not None and ask is not None:
        return (bid[0] + ask[0]) / 2.0
    if ask is not None:
        return float(ask[0])
    if bid is not None:
        return float(bid[0])
    return 0.0


class ImpactEstimator:
    """估计执行单对市场的冲击。"""

    def __init__(self, session: ReplaySession) -> None:
        self.session = session

    def estimate(self, schedule: ExecutionSchedule) -> ImpactResult:
        if self.session.engine.backend != "python":
            raise NotImplementedError("ImpactEstimator requires Python per-fill execution evidence")
        if schedule.side not in (-1, 1):
            raise ValueError("side must be 1 or -1")
        if schedule.total_volume < 0 or schedule.n_child < 1:
            raise ValueError("total_volume must be nonnegative and n_child must be positive")
        self.session.validate_pending()
        self.session.validate_timestamp(schedule.start_time_ms)
        child_vol = schedule.total_volume // max(schedule.n_child, 1)
        span = max(schedule.end_time_ms - schedule.start_time_ms, 1)
        children = []
        for i in range(schedule.n_child):
            t = schedule.start_time_ms + span * i // max(schedule.n_child, 1)
            vol = (
                child_vol
                if i < schedule.n_child - 1
                else (schedule.total_volume - child_vol * (schedule.n_child - 1))
            )
            if vol > 0:
                self.session.validate_timestamp(t)
                children.append((i, t, vol))
        mid_before = _mid(self.session)
        fill_start = len(self.session.fills)
        child_ids: set[str] = set()
        for i, t, vol in children:
            # 按计划提交时的对手最优价构造限价单。
            if schedule.side == 1:
                ask = self.session.engine.lob.best_ask()
                price = ask[0] if ask is not None else int(mid_before + 1)
            else:
                bid = self.session.engine.lob.best_bid()
                price = bid[0] if bid is not None else int(mid_before - 1)
            order_id = self.session.reserve_order_id(f"IMPACT{i}")
            child_ids.add(order_id)
            self.session.add_intervention(
                InterventionOrder(
                    time_ms=t, side=schedule.side, price=int(price), volume=vol, order_id=order_id
                )
            )
        self.session.run()
        mid_after = _mid(self.session)
        if mid_before > 0:
            slippage = (mid_after - mid_before) / mid_before * 10000.0
            # 买入冲击应为正（价格推高），卖出为负；统一取方向修正
            slippage *= schedule.side
        else:
            slippage = 0.0
        fills = tuple(
            fill
            for fill in self.session.fills[fill_start:]
            if (fill.buy_id if schedule.side == 1 else fill.sell_id) in child_ids
        )
        filled_volume = sum(fill.volume for fill in fills)
        vwap = (
            sum(fill.price * fill.volume for fill in fills) / filled_volume
            if filled_volume
            else None
        )
        execution_slippage = (
            (vwap / mid_before - 1) * 10000 * schedule.side
            if vwap is not None and mid_before > 0
            else None
        )
        return ImpactResult(
            mid_before=mid_before,
            mid_after=mid_after,
            slippage_bps=slippage,
            filled_volume=filled_volume,
            unfilled_volume=schedule.total_volume - filled_volume,
            execution_vwap=vwap,
            execution_slippage_bps=execution_slippage,
            fills=fills,
        )
