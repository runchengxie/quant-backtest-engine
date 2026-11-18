# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/backtest/minute.py
# Original SHA256: 82e0041c16c53b4f7a3f181fcb3e07233a15da39e4c1869597f205a712728814
"""Explicit minute execution API; importing this module loads the simulator."""

from quant_backtest_core._minute.capital_flows import CapitalFlow
from quant_backtest_core._minute.corporate_actions import CorporateAction
from quant_backtest_core._minute.minute_execution import (
    MinuteDecisionState,
    MinuteExecutionConfig,
    MinuteExecutionResult,
    simulate_minute_execution,
)
from quant_backtest_core._minute.valuation_events import ValuationEvent

__all__ = [
    "CapitalFlow",
    "CorporateAction",
    "MinuteDecisionState",
    "MinuteExecutionConfig",
    "MinuteExecutionResult",
    "ValuationEvent",
    "simulate_minute_execution",
]
