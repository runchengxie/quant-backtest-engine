"""Execution assumptions (entry/exit, costs, slippage, constraints).

Public symbols are re-exported from the private submodules:

* :mod:`portfolio_backtester._execution_models`
* :mod:`portfolio_backtester._execution_build`

The split is behavior-preserving; external imports from this module are unchanged.
"""

from __future__ import annotations

from ._execution_build import (
    build_cost_model as build_cost_model,
)
from ._execution_build import (
    build_entry_policy as build_entry_policy,
)
from ._execution_build import (
    build_execution_model as build_execution_model,
)
from ._execution_build import (
    build_exit_policy as build_exit_policy,
)
from ._execution_build import (
    build_selection_constraints as build_selection_constraints,
)
from ._execution_build import (
    build_slippage_model as build_slippage_model,
)
from ._execution_build import (
    describe_cost_model as describe_cost_model,
)
from ._execution_build import (
    describe_execution_model as describe_execution_model,
)
from ._execution_build import (
    describe_selection_constraints as describe_selection_constraints,
)
from ._execution_build import (
    describe_slippage_model as describe_slippage_model,
)
from ._execution_build import (
    l2_price_tiered_slippage as l2_price_tiered_slippage,
)
from ._execution_build import (
    required_pricing_columns as required_pricing_columns,
)
from ._execution_models import (
    BpsCostModel as BpsCostModel,
)
from ._execution_models import (
    BpsSlippageModel as BpsSlippageModel,
)
from ._execution_models import (
    CostModel as CostModel,
)
from ._execution_models import (
    DetailedTradeFeeModel as DetailedTradeFeeModel,
)
from ._execution_models import (
    EntryPolicy as EntryPolicy,
)
from ._execution_models import (
    ExecutionModel as ExecutionModel,
)
from ._execution_models import (
    ExitFallbackPolicy as ExitFallbackPolicy,
)
from ._execution_models import (
    ExitPolicy as ExitPolicy,
)
from ._execution_models import (
    ExitPricePolicy as ExitPricePolicy,
)
from ._execution_models import (
    NoCostModel as NoCostModel,
)
from ._execution_models import (
    NoSlippageModel as NoSlippageModel,
)
from ._execution_models import (
    ParticipationSlippageModel as ParticipationSlippageModel,
)
from ._execution_models import (
    SelectionConstraints as SelectionConstraints,
)
from ._execution_models import (
    SideBpsCostModel as SideBpsCostModel,
)
from ._execution_models import (
    SlippageModel as SlippageModel,
)
from .dated_fees import (
    DatedFeeQuote as DatedFeeQuote,
)
from .dated_fees import (
    DatedFeeSchedule as DatedFeeSchedule,
)
from .dated_fees import (
    DatedTradeFeeModel as DatedTradeFeeModel,
)
from .dated_fees import (
    FeeQuoteContext as FeeQuoteContext,
)
from .dated_fees import (
    FeeSchedulePeriod as FeeSchedulePeriod,
)

__all__ = [
    "BpsCostModel",
    "BpsSlippageModel",
    "CostModel",
    "DatedFeeQuote",
    "DatedFeeSchedule",
    "DatedTradeFeeModel",
    "DetailedTradeFeeModel",
    "EntryPolicy",
    "ExecutionModel",
    "ExitFallbackPolicy",
    "ExitPolicy",
    "ExitPricePolicy",
    "FeeQuoteContext",
    "FeeSchedulePeriod",
    "NoCostModel",
    "NoSlippageModel",
    "ParticipationSlippageModel",
    "SelectionConstraints",
    "SideBpsCostModel",
    "SlippageModel",
    "build_cost_model",
    "build_entry_policy",
    "build_execution_model",
    "build_exit_policy",
    "build_selection_constraints",
    "build_slippage_model",
    "describe_cost_model",
    "describe_execution_model",
    "describe_selection_constraints",
    "describe_slippage_model",
    "l2_price_tiered_slippage",
    "required_pricing_columns",
]
