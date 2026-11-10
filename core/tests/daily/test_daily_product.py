import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from quant_backtest_engine.product import (
    manifest_to_json,
    parse_manifest,
    parse_result,
    result_to_json,
)

from quant_backtest_core.backends.daily import DailyBackend
from quant_backtest_core.backends.protocol import BackendContext
from quant_backtest_core.daily.contracts import ExecutionCalendar
from quant_backtest_core.daily.execution_sim import simulate_capacity_execution
from quant_backtest_core.daily.period_replay import run_period_replay
from quant_backtest_core.daily.position_backtest import PositionBacktestResult

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures/product"


def wire():
    return json.loads((FIXTURES / "daily.json").read_text())


def test_daily_product_preserves_all_raw_tables_and_unknown_evidence(tmp_path):
    manifest = parse_manifest(wire())
    context = BackendContext(FIXTURES, tmp_path)
    backend = DailyBackend(context)
    assert backend.descriptor().checkpoint_schemas == ()
    result = backend.run(manifest, context)
    tables = {t.name: t for t in result.tables}
    assert tables["daily"].status == "available"
    assert [r["cash"] for r in tables["daily"].rows] == ["0.0"] * 3
    assert [r["symbol"] for r in tables["fills"].rows] == ["A"]
    for name in ("cash", "capital_flows", "admissions", "reservations", "valuations"):
        assert tables[name].status == "unavailable"
        assert tables[name].rows == ()
    raw = tmp_path / result.raw_result.uri
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == result.raw_result.sha256
    native = json.loads(raw.read_text())
    assert set(native["unified_ledger"]) == {
        "targets",
        "orders",
        "fills",
        "daily_positions",
        "daily_cash",
        "daily_nav",
        "cost_breakdown",
        "turnover_breakdown",
    }
    assert native["tables"]["actions"] is None
    assert result.summary["cumulative_return"] == "0.0"
    assert parse_result(result_to_json(result)) == result
    with pytest.raises(Exception, match="overwrite"):
        backend.run(manifest, context)


def test_capacity_is_not_advertised_as_a_cash_or_fee_ledger(tmp_path):
    value = wire()
    value["settings"]["mode"] = "capacity"
    result = DailyBackend(BackendContext(FIXTURES, tmp_path)).run(
        parse_manifest(value), BackendContext(FIXTURES, tmp_path)
    )
    tables = {t.name: t for t in result.tables}
    assert tables["daily"].status == tables["cash"].status == tables["fees"].status == "unavailable"


@pytest.mark.parametrize(
    "change",
    [
        lambda w: w["inline_inputs"]["pricing"][0].update(close=10.0),
        lambda w: w["settings"]["config"].update(portfolio_value="1001"),
        lambda w: w["settings"].update(factory="arbitrary.module"),
        lambda w: w["settings"]["fee_model"].update(kind="module.factory"),
        lambda w: w["settings"]["decision_clocks"]["2020-01-02"].update(entry_ns=123),
        lambda w: w["settings"]["layout"].update(currency="USD"),
    ],
)
def test_sdk_rejects_invalid_daily_transport(change):
    value = wire()
    value["settings"]["fee_model"] = {
        "kind": "detailed",
        **{
            k: "0"
            for k in (
                "buy_commission_bps",
                "sell_commission_bps",
                "sell_stamp_duty_bps",
                "transfer_fee_bps",
                "min_commission",
                "buy_slippage_bps",
                "sell_slippage_bps",
                "portfolio_value",
            )
        },
    }
    change(value)
    with pytest.raises(ValueError):
        parse_manifest(value)


def test_input_artifacts_are_revalidated_before_execution(tmp_path):
    value = wire()
    rows = copy.deepcopy(value["inline_inputs"].pop("pricing"))
    rows[0]["close"] = 10.0
    data = json.dumps(rows).encode()
    (tmp_path / "pricing.json").write_bytes(data)
    (tmp_path / "daily-calendar.json").write_bytes((FIXTURES / "daily-calendar.json").read_bytes())
    value["inputs"] = {
        "pricing": {
            "uri": "pricing.json",
            "sha256": hashlib.sha256(data).hexdigest(),
            "media_type": "application/json",
        }
    }
    context = BackendContext(tmp_path, tmp_path / "out")
    with pytest.raises(ValueError):
        DailyBackend(context).run(parse_manifest(value), context)
    assert not (tmp_path / "out").exists()


def test_original_liquid_golden_is_diagnostic_period_evidence_only():
    expected = json.loads(
        (Path(__file__).parent / "fixtures/liquid_long_only.expected.json").read_text()
    )
    positions = pd.DataFrame(
        {
            "rebalance_date": ["20200101"] * 2,
            "entry_date": ["20200102"] * 2,
            "symbol": ["AAA", "BBB"],
            "weight": [0.75, 0.25],
            "side": ["long"] * 2,
        }
    )
    prices = pd.DataFrame(
        [
            {"trade_date": d, "symbol": s, "close": p}
            for d, s, p in [
                ("20200102", "AAA", 10.0),
                ("20200102", "BBB", 20.0),
                ("20200103", "AAA", 11.0),
                ("20200103", "BBB", 18.0),
            ]
        ]
    )
    periods = pd.DataFrame(
        {"rebalance_date": ["20200101"], "entry_date": ["20200102"], "exit_date": ["20200103"]}
    )
    result = run_period_replay(
        positions=positions,
        pricing=prices,
        periods=periods,
        calendar=ExecutionCalendar.from_dates("Asia/Shanghai", ("2020-01-02", "2020-01-03")),
        config={"transaction_cost_bps": 10.0},
    )
    assert isinstance(result, PositionBacktestResult)
    assert result.net_returns.iloc[0].net_return == pytest.approx(
        expected["performance"][0]["net_return"]
    )
    assert result.gross_returns.iloc[0].gross_return == pytest.approx(
        expected["performance"][0]["gross_return"]
    )
    assert result.net_returns.iloc[0].period_end == expected["performance"][0]["period_end"]
    assert result.summary["schema"] == "position_backtest.v1"
    for attribute in ("daily", "orders", "fills", "cash", "holdings"):
        assert not hasattr(result, attribute)
    assert not expected["capabilities"]["daily_ledger"]
    assert not expected["capabilities"]["order_lifecycle"]
    with pytest.raises(ValueError, match="calendar coverage"):
        run_period_replay(
            positions=positions,
            pricing=prices,
            periods=periods,
            calendar=ExecutionCalendar.from_dates("Asia/Shanghai", ("2020-01-02",)),
            config={},
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda w: w["settings"]["layout"]["liquidity_units"].append(
            {"column": "amount", "unit": "CNY"}
        ),
        lambda w: w["settings"]["layout"]["liquidity_units"].append(
            {"column": "unknown", "unit": "CNY"}
        ),
        lambda w: w["settings"]["layout"]["liquidity_units"][0].update(unit="USD"),
        lambda w: w["settings"]["layout"]["liquidity_units"][0].update(extra="unknown"),
        lambda w: w["settings"].update(fee_model=[]),
        lambda w: w["inline_inputs"]["pricing"][0].update(close="1" + "0" * 400),
        lambda w: w["inline_inputs"]["pricing"][0].update(close="0." + "0" * 400 + "1"),
    ],
)
def test_daily_wire_rejects_duplicate_unknown_or_unrepresentable_units_and_numbers(change):
    value = wire()
    change(value)
    with pytest.raises(ValueError):
        parse_manifest(value)


def test_daily_wire_roundtrip_preserves_column_units_and_exact_clocks(tmp_path):
    value = wire()
    manifest = parse_manifest(value)
    assert manifest_to_json(manifest) == value
    assert parse_manifest(manifest_to_json(manifest)) == manifest
    backend = DailyBackend(BackendContext(FIXTURES, tmp_path))
    request = backend._prepare(manifest, backend.context)
    assert dict(request.layout.liquidity_units) == {"amount": "CNY"}
    result = backend.run(manifest, backend.context)
    raw = json.loads((tmp_path / result.raw_result.uri).read_text())
    assert raw["decision_clocks"] == value["settings"]["decision_clocks"]
    for name, frame in raw["owner_tables"].items():
        if frame is not None:
            assert frame["columns"] == raw["tables"][name]["columns"]
            assert len(frame["dtypes"]) == len(frame["columns"])
            assert isinstance(frame["index_dtype"], str)
            assert isinstance(frame["columns_dtype"], str)
            assert len(frame["data"]) == len(frame["index"])
    assert set(raw["owner_unified_ledger"]) == set(raw["unified_ledger"])


@pytest.mark.parametrize(
    "control",
    [
        "enforce_price_limits",
        "enforce_listing_status",
        "enforce_t1",
        "round_lot",
        "sell_round_lot",
        "unfilled_buy_action",
        "unfilled_sell_action",
    ],
)
def test_capacity_product_rejects_unsupported_rules_without_outputs(control, tmp_path):
    value = wire()
    value["settings"]["mode"] = "capacity"
    config = value["settings"]["config"]
    config[control] = (
        "cancel"
        if control.startswith("unfilled_")
        else 100
        if control in ("round_lot", "sell_round_lot")
        else True
    )
    if control == "enforce_price_limits":
        config.update(limit_up_col="limit_up", limit_down_col="limit_down")
        for row in value["inline_inputs"]["pricing"]:
            row.update(limit_up=True, limit_down=False)
    elif control == "enforce_listing_status":
        config["listing_status_col"] = "listing_status"
        for row in value["inline_inputs"]["pricing"]:
            row["listing_status"] = "delisted"
    context = BackendContext(FIXTURES, tmp_path / "not-created")
    with patch(
        "quant_backtest_core.daily.runner.simulate_capacity_execution",
        wraps=simulate_capacity_execution,
    ) as owner:
        with pytest.raises(ValueError, match=f"capacity.*{control}"):
            DailyBackend(context).run(parse_manifest(value), context)
        owner.assert_not_called()
    assert not context.output_root.exists()
