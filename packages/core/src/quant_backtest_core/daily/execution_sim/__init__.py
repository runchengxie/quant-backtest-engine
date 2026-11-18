"""Lazy public execution surface; importing config never loads the runner."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CorporateAction": ("quant_backtest_core._minute.corporate_actions", "CorporateAction"),
    "SELL_UNTIL_NEXT_REBALANCE": (
        "quant_backtest_core.daily.execution_sim.config",
        "SELL_UNTIL_NEXT_REBALANCE",
    ),
    "ExecutionSimConfig": ("quant_backtest_core.daily.execution_sim.config", "ExecutionSimConfig"),
    "build_execution_sim_config": (
        "quant_backtest_core.daily.execution_sim.config",
        "build_execution_sim_config",
    ),
    "describe_execution_sim_config": (
        "quant_backtest_core.daily.execution_sim.config",
        "describe_execution_sim_config",
    ),
    "required_execution_sim_columns": (
        "quant_backtest_core.daily.execution_sim.config",
        "required_execution_sim_columns",
    ),
    "prepare_execution_tables": (
        "quant_backtest_core.daily.execution_sim.core",
        "prepare_execution_tables",
    ),
    "simulate_capacity_execution": (
        "quant_backtest_core.daily.execution_sim.core",
        "simulate_capacity_execution",
    ),
    "simulate_execution_adjusted_nav": (
        "quant_backtest_core.daily.execution_sim.core",
        "simulate_execution_adjusted_nav",
    ),
    "simulate_ideal_daily_nav": (
        "quant_backtest_core.daily.execution_sim.core",
        "simulate_ideal_daily_nav",
    ),
    "audit_delisting_exits": (
        "quant_backtest_core.daily.execution_sim.delisting",
        "audit_delisting_exits",
    ),
    "PreparedExecutionTables": (
        "quant_backtest_core.daily.execution_sim.models",
        "PreparedExecutionTables",
    ),
    "TradeFeeModel": ("quant_backtest_core.daily.execution_sim.models", "TradeFeeModel"),
    "describe_trade_fee_model": (
        "quant_backtest_core.daily.execution_sim.models",
        "describe_trade_fee_model",
    ),
    "ExecutionAdjustedNavResult": (
        "quant_backtest_core.daily.execution_sim.results",
        "ExecutionAdjustedNavResult",
    ),
    "ExecutionSimResult": ("quant_backtest_core.daily.execution_sim.results", "ExecutionSimResult"),
    "UnifiedLedger": ("quant_backtest_core.daily.execution_sim.results", "UnifiedLedger"),
    "to_unified_ledger": ("quant_backtest_core.daily.execution_sim.results", "to_unified_ledger"),
}
__all__ = [
    "CorporateAction",
    "SELL_UNTIL_NEXT_REBALANCE",
    "ExecutionAdjustedNavResult",
    "ExecutionSimConfig",
    "ExecutionSimResult",
    "PreparedExecutionTables",
    "TradeFeeModel",
    "UnifiedLedger",
    "audit_delisting_exits",
    "build_execution_sim_config",
    "describe_execution_sim_config",
    "describe_trade_fee_model",
    "prepare_execution_tables",
    "required_execution_sim_columns",
    "simulate_capacity_execution",
    "simulate_execution_adjusted_nav",
    "simulate_ideal_daily_nav",
    "to_unified_ledger",
]


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
