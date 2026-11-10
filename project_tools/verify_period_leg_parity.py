"""Execute explicit synthetic period-leg cases against actual installed owners.

Run --owner legacy in the pinned original environment, then --owner core in
an ordinary installed Core environment. Compare the two captures with --compare.
Captures are trusted local test artifacts, never untrusted serialized requests.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import pickle
import sys
from dataclasses import fields, is_dataclass, replace
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd


def collect(owner):
    prefix = (
        "quant_platform._portfolio"
        if owner == "legacy"
        else "quant_backtest_core.daily"
    )
    leg = importlib.import_module(
        prefix + (".leg_helpers" if owner == "legacy" else ".leg_financial")
    )
    period = importlib.import_module(prefix + ".period_turnover")
    pricing = importlib.import_module(prefix + ".pricing")
    accounting = importlib.import_module(prefix + ".trade_accounting")
    types = importlib.import_module(prefix + ".types")
    models = importlib.import_module(prefix + "._execution_models")
    identities = {}
    values = {}
    dates = list(pd.date_range("2026-01-05", periods=5))
    table = pd.DataFrame(
        {
            "A": [10.0, 12.0, 11.0, 13.0, 14.0],
            "B": [20.0, np.nan, 18.0, 19.0, 20.0],
            "C": [5.0] * 5,
        },
        index=dates,
    )
    amounts = {
        "amount": pd.DataFrame(
            {"A": [1000.0] * 5, "B": [2000.0] * 5, "C": [500.0] * 5}, index=dates
        )
    }

    def project(value):
        if is_dataclass(value):
            identities[type(value).__name__] = type(value).__module__
            result = {
                field.name: project(getattr(value, field.name))
                for field in fields(value)
            }
            result["__class_name__"] = type(value).__name__
            for name in (
                "cost_breakdown",
                "turnover_breakdown",
                "net",
                "total_cost",
                "target_entered_count",
                "target_exited_count",
                "target_overlap_count",
                "execution_data_available",
            ):
                if hasattr(type(value), name):
                    result["property:" + name] = project(getattr(value, name))
            return result
        if isinstance(value, dict):
            return {key: project(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return type(value)(project(item) for item in value)
        return value

    def retain(key, call):
        try:
            actual = call()
        except (KeyError, ValueError, IndexError, TypeError) as exc:
            values[key] = {
                "exception": (type(exc).__module__, type(exc).__name__, str(exc))
            }
            return None
        values[key] = project(actual)
        return actual

    weights = {
        "full": pd.Series({"A": 0.6, "B": 0.4}),
        "cash": pd.Series({"A": 0.3, "B": 0.2}),
        "zero": pd.Series({"A": 0.0, "B": 0.0}),
        "empty": pd.Series(dtype=float),
        "dirty": pd.Series({"A": 0.3, "B": np.nan, "C": np.inf}),
    }
    previous = {
        "initial": types.BacktestPositionState(),
        "cash": types.BacktestPositionState(
            holdings=set(), weights=pd.Series(dtype=float)
        ),
        "prior": types.BacktestPositionState(
            holdings={"A", "B"},
            weights=pd.Series({"A": 0.4, "B": 0.2}),
            entry_date=dates[0],
            entry_prices=pd.Series({"A": 10.0, "B": 20.0}),
            target_holdings={"A", "C"},
            target_weights=pd.Series({"A": 0.6, "C": 0.1}),
        ),
        "missing": types.BacktestPositionState(
            holdings={"A", "B"},
            weights=pd.Series({"A": 0.4, "B": 0.2}),
            entry_date=dates[0],
            entry_prices=pd.Series({"A": np.nan, "B": 20.0}),
        ),
    }
    costs = {
        "bps": models.BpsCostModel(12.0),
        "side": models.SideBpsCostModel(1.0, 2.0, 3.0, 4.0, 5.0),
        "minimum": models.DetailedTradeFeeModel(
            buy_commission_bps=1.0,
            sell_commission_bps=2.0,
            min_commission=5.0,
            buy_slippage_bps=0.0,
            sell_slippage_bps=0.0,
            portfolio_value=100.0,
        ),
    }
    slips = {
        "none": models.NoSlippageModel(),
        "participation": models.ParticipationSlippageModel(
            base_bps=2.0,
            impact_bps=3.0,
            portfolio_value=100.0,
            max_participation=0.05,
        ),
    }
    for state_name, state in previous.items():
        for weight_name, weight in weights.items():
            retain(
                "turnover-report/" + state_name + "/" + weight_name,
                lambda leg=leg, state=state, weight=weight: (
                    leg._build_leg_turnover_report(
                        state,
                        weight,
                        pd.Series({"A": -0.1, "C": 0.2}),
                    )
                ),
            )
    built = []
    for side in ("long", "short"):
        for state_name, state in previous.items():
            for weight_name, weight in weights.items():
                for preserve in (False, True):
                    for cost_name, cost in costs.items():
                        for slip_name, slip in slips.items():
                            key = "/".join(
                                (
                                    side,
                                    state_name,
                                    weight_name,
                                    str(preserve),
                                    cost_name,
                                    slip_name,
                                )
                            )
                            result = retain(
                                "leg/" + key,
                                lambda amounts=amounts, cost=cost, dates=dates, leg=leg, list=list, np=np, pd=pd, preserve=preserve, side=side, slip=slip, state=state, table=table, weight=weight: (
                                    leg._build_backtest_leg_result(
                                        holdings=list(weight.index),
                                        target_weights=pd.Series({"A": 0.5, "C": 0.1}),
                                        weights=weight,
                                        entry_prices=pd.Series(
                                            {"A": 12.0, "B": 20.0, "C": 5.0}
                                        ),
                                        exit_prices=pd.Series(
                                            {"A": 14.0, "B": 18.0, "C": np.nan}
                                        ),
                                        period_exit_idx=4 if side == "long" else 3,
                                        entry_idx=1,
                                        entry_date=dates[1],
                                        trade_dates=dates,
                                        entry_price_table=table,
                                        side=side,
                                        previous=state,
                                        cost_model=cost,
                                        slippage_model=slip,
                                        amount_tables=amounts,
                                        preserve_gross_exposure=preserve,
                                    )
                                ),
                            )
                            if result is not None:
                                retain(
                                    "state/" + key,
                                    lambda dates=dates, leg=leg, result=result: (
                                        leg._next_position_state(
                                            result, entry_date=dates[1]
                                        )
                                    ),
                                )
                                retain(
                                    "period/" + key,
                                    lambda period=period, result=result: (
                                        period.period_result_from_leg(result)
                                    ),
                                )
                                built.append(result)
    for i in range(0, len(built) - 1, 2):
        left, right = built[i], built[-i - 1]
        retain(
            "pair/" + str(i),
            lambda dates=dates, left=left, period=period, right=right: (
                period.period_result_from_legs(left, right, trade_dates=dates)
            ),
        )
    base = built[0]
    for initial in (True, False):
        for targets in ((), ("C",)):
            cash = replace(
                base,
                holdings=[],
                weights=pd.Series(dtype=float),
                is_initial=initial,
                target_holdings=targets,
                target_weights=pd.Series({"C": 0.2})
                if targets
                else pd.Series(dtype=float),
            )
            retain(
                "cash-state/" + str((initial, targets)),
                lambda cash=cash, dates=dates, leg=leg: leg._next_position_state(
                    cash, entry_date=dates[1]
                ),
            )
    diagnostics = (
        (
            "unknown",
            {field.name: None for field in fields(base) if field.default is None},
        ),
        (
            "observed",
            {
                "executed_buy": 0.1,
                "executed_sell": 0.2,
                "executed_gross": 0.3,
                "executed_full_l1": 0.3,
                "executed_half_l1": 0.15,
                "executed_cost": 0.002,
                "target_name_turnover": 0.4,
                "target_weight_full_l1": 0.6,
                "target_weight_half_l1": 0.3,
            },
        ),
    )
    for name, updates in diagnostics:
        left = replace(base, **updates, target_entered_names=("Z", "A"), exit_idx=1)
        right = replace(base, **updates, target_entered_names=("A", "B"), exit_idx=4)
        retain(
            "diagnostic-pair/" + name,
            lambda dates=dates, left=left, period=period, right=right: (
                period.period_result_from_legs(left, right, trade_dates=dates)
            ),
        )
    for state_name, state in previous.items():
        for target_name, target in {
            **weights,
            "negative": pd.Series({"A": -1.0, "B": 0.0}),
            "invalid": pd.Series({"A": np.nan, "B": np.inf}),
        }.items():
            for mark in ("available", "missing", "absent-date", "nonpositive"):
                marks = table if mark != "nonpositive" else table * -1
                at = (
                    dates[1]
                    if mark != "absent-date"
                    else dates[-1] + pd.Timedelta(days=1)
                )
                prices = state.entry_prices if mark != "missing" else None
                retain(
                    "legacy-trades/" + f"{state_name}/{target_name}/{mark}",
                    lambda accounting=accounting, at=at, marks=marks, prices=prices, state=state, target=target: (
                        accounting.compute_trade_summary(
                            state.weights,
                            prices,
                            state.entry_date,
                            target,
                            at,
                            price_table=marks,
                        )
                    ),
                )
                if state.weights is not None:
                    retain(
                        "legacy-drift/" + f"{state_name}/{target_name}/{mark}",
                        lambda accounting=accounting, at=at, marks=marks, prices=prices, state=state: (
                            accounting.drift_previous_weights(
                                state.weights,
                                prices,
                                state.entry_date,
                                at,
                                price_table=marks,
                            )
                        ),
                    )
    retain(
        "legacy-none-target",
        lambda accounting=accounting, dates=dates, table=table: (
            accounting.compute_trade_summary(
                None,
                None,
                None,
                None,
                dates[0],
                price_table=table,
            )
        ),
    )
    assert accounting._compute_trade_summary is accounting.compute_trade_summary
    assert accounting._drift_previous_weights is accounting.drift_previous_weights
    for slip_name, slip in slips.items():
        for tables_name, tables in (("available", amounts), ("missing", {})):
            for at in (dates[1], dates[-1] + pd.Timedelta(days=1)):
                retain(
                    "pricing/" + str((slip_name, tables_name, at)),
                    lambda at=at, pricing=pricing, slip=slip, tables=tables: (
                        pricing.slippage_pricing_row(
                            slippage_model=slip,
                            amount_tables=tables,
                            entry_date=at,
                        )
                    ),
                )
    calls = []

    class CostRecorder:
        def cost(self, *args, **kwargs):
            calls.append(("cost", args, kwargs))
            return 0.003

    class SlippageRecorder:
        def cost(self, *args, **kwargs):
            calls.append(("slippage", args, kwargs))
            return 0.002

    retain(
        "method-contract",
        lambda CostRecorder=CostRecorder, SlippageRecorder=SlippageRecorder, dates=dates, leg=leg, pd=pd, previous=previous, table=table: (
            leg._build_backtest_leg_result(
                holdings=["A"],
                target_weights=pd.Series({"A": 0.3}),
                weights=pd.Series({"A": 0.2}),
                entry_prices=pd.Series({"A": 12.0}),
                exit_prices=pd.Series({"A": 14.0}),
                period_exit_idx=4,
                entry_idx=1,
                entry_date=dates[1],
                trade_dates=dates,
                entry_price_table=table,
                side="short",
                previous=previous["prior"],
                cost_model=CostRecorder(),
                slippage_model=SlippageRecorder(),
                amount_tables={},
                preserve_gross_exposure=True,
            )
        ),
    )
    values["exact-method-calls"] = project(calls)
    for name, module in (
        ("leg", leg),
        ("period", period),
        ("pricing", pricing),
        ("trade", accounting),
    ):
        names = {
            "leg": (
                "_build_backtest_leg_result",
                "_build_leg_turnover_report",
                "_next_position_state",
            ),
            "period": (
                "period_result_from_leg",
                "period_result_from_legs",
                "_optional_sum",
                "_merged_names",
            ),
            "pricing": ("slippage_pricing_row",),
            "trade": ("compute_trade_summary", "drift_previous_weights"),
        }[name]
        for symbol in names:
            values["signature/" + symbol] = str(
                inspect.signature(getattr(module, symbol))
            )
    values["signature/BacktestPeriodResult"] = str(
        inspect.signature(types.BacktestPeriodResult)
    )
    values["period-defaults"] = project(
        types.BacktestPeriodResult(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, dates[0])
    )
    modules = {}
    for name, module in sorted(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_file():
            source = Path(path)
            modules[name] = {
                "path": str(source.resolve()),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        else:
            spec = getattr(module, "__spec__", None)
            modules[name] = {"origin": getattr(spec, "origin", None)}
    if owner == "core":
        forbidden = (
            "quant_platform",
            "quant_backtest_runtime",
            "research_contracts",
            "torch",
        )
        assert not any(name.startswith(forbidden) for name in sys.modules)
        for name, record in modules.items():
            if name.startswith(("quant_backtest_core", "quant_backtest_engine")):
                assert Path(record["path"]).is_relative_to(Path(sys.prefix))
    return {
        "values": values,
        "identities": identities,
        "modules": modules,
        "dependencies": {
            dist.metadata["Name"]: dist.version for dist in metadata.distributions()
        },
        "python": sys.version,
        "prefix": sys.prefix,
    }


def compare(left, right, *, allow_lean_string_storage=False):
    count = {"nodes": 0, "series": 0, "frames": 0}
    storage_exceptions = []

    def reconcile_string_storage(a, b, location):
        if a.dtype == b.dtype:
            return b
        if not allow_lean_string_storage:
            return b
        old, new = a.dtype, b.dtype
        if not (isinstance(old, pd.StringDtype) and isinstance(new, pd.StringDtype)):
            return b
        assert old.storage == "pyarrow" and new.storage == "python", location
        assert pd.isna(old.na_value) and pd.isna(new.na_value), location
        storage_exceptions.append(
            {
                "location": location,
                "old_dtype": repr(old),
                "new_dtype": repr(new),
                "old_storage": old.storage,
                "new_storage": new.storage,
            }
        )
        return b.astype(old)

    def same(a, b, location):
        count["nodes"] += 1
        if isinstance(a, pd.Series):
            if allow_lean_string_storage:
                b = b.copy()
                b.index = reconcile_string_storage(
                    a.index, b.index, location + "/index"
                )
                b = reconcile_string_storage(a, b, location + "/values")
            pd.testing.assert_series_equal(a, b, check_exact=True)
            count["series"] += 1
        elif isinstance(a, pd.DataFrame):
            pd.testing.assert_frame_equal(a, b, check_exact=True)
            count["frames"] += 1
        elif isinstance(a, dict):
            assert a.keys() == b.keys(), location
            for key in a:
                same(a[key], b[key], location + "/" + str(key))
        elif isinstance(a, (tuple, list)):
            assert type(a) is type(b) and len(a) == len(b), location
            for i, (x, y) in enumerate(zip(a, b)):
                same(x, y, location + "/" + str(i))
        elif isinstance(a, float) and np.isnan(a):
            assert isinstance(b, float) and np.isnan(b), location
        else:
            assert type(a) is type(b) and a == b, (location, a, b)

    same(left["values"], right["values"], "values")
    assert left["identities"].keys() == right["identities"].keys()
    return {
        "status": "PASS",
        "cases": len(left["values"]),
        **count,
        "identity_only_differences": {
            name: [old, right["identities"][name]]
            for name, old in left["identities"].items()
        },
        "dtype_exceptions": storage_exceptions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=("legacy", "core"))
    parser.add_argument("--allow-lean-string-storage", action="store_true")
    parser.add_argument("--compare", nargs=2, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    assert sys.flags.isolated, "Use python -I -B for installed acceptance"
    if args.compare:
        with args.compare[0].open("rb") as stream:
            left = pickle.load(stream)
        with args.compare[1].open("rb") as stream:
            right = pickle.load(stream)
        report = compare(
            left, right, allow_lean_string_storage=args.allow_lean_string_storage
        )
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps(report, indent=2))
    else:
        capture = collect(args.owner)
        with args.output.open("xb") as stream:
            pickle.dump(capture, stream, protocol=5)
        with args.output.with_suffix(".closure.json").open("x") as stream:
            json.dump(
                {key: value for key, value in capture.items() if key != "values"},
                stream,
                indent=2,
            )
        print(
            "CAPTURE",
            args.owner,
            len(capture["values"]),
            "cases",
            len(capture["modules"]),
            "modules",
        )


if __name__ == "__main__":
    main()
