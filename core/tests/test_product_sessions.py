"""Product sessions exercised with installed wheels."""

import json
from pathlib import Path

import pytest
from quant_backtest_engine.product import loads_manifest, result_to_json

from quant_backtest_core import BackendContext

ROOT = Path(__file__).resolve().parents[2]


def setup(tmp_path):
    import quant_backtest_core.sessions as sessions

    manifest = loads_manifest((ROOT / "fixtures/product/minute-session.json").read_text())
    return sessions, manifest, BackendContext(ROOT / "fixtures/product", tmp_path)


def test_public_session_interface_exists():
    import importlib.util

    assert importlib.util.find_spec("quant_backtest_core.sessions") is not None


@pytest.mark.parametrize(
    "variant", ["baseline", "zero-delay", "valuation", "unknown", "small-weight", "small-fee"]
)
def test_every_boundary_restores_complete_financial_payload(tmp_path, variant):
    sessions, manifest, context = setup(tmp_path)
    from quant_backtest_engine.product import manifest_to_json, parse_manifest

    wire = manifest_to_json(manifest)
    if variant == "small-weight":
        for row in wire["inline_inputs"]["targets"]:
            row["weight"] = "0.00001"
    if variant == "small-fee":
        wire["settings"]["config"]["commission_minimum_cny"] = "0"
        wire["settings"]["config"]["buy_fee_bp"] = "0.0000001"
    if variant == "zero-delay":
        wire["settings"]["report_delay_seconds"] = "0"
    if variant == "valuation":
        instant = wire["inline_inputs"]["bars"][3]["time"]
        wire["tapes"]["valuation_events"] = [
            {
                "event_id": "residual",
                "symbol": "A",
                "effective_time": instant,
                "available_time": instant,
                "value_per_share": "4.5",
                "basis": "declared",
                "source": "synthetic",
            }
        ]
        for row in wire["inline_inputs"]["bars"]:
            if int(row["time"]) >= int(instant):
                row["tradable"] = False
    if variant == "unknown":
        wire["inline_inputs"]["bars"] = wire["inline_inputs"]["bars"][:6]
    manifest = parse_manifest(wire)
    expected = result_to_json(sessions.open_session(manifest, context=context).finish())
    fills = next(table for table in expected["tables"] if table["name"] == "fills")["rows"]
    if variant == "small-weight":
        assert fills == []  # This target is below the native buy-lot threshold.
    if variant == "small-fee":
        assert [row["commission"] for row in fills] == [
            "0.000000010005000000000001",
            "0.000000010014999999999999",
        ]
        assert [row["quantity"] for row in fills] == ["100", "100"]
    if variant == "unknown":
        assert (
            next(t for t in expected["tables"] if t["name"] == "daily")["rows"][-1]["nav"] is None
        )
    session = sessions.open_session(
        manifest, context=BackendContext(context.artifact_root, tmp_path / "source")
    )
    checkpoints = [session.checkpoint()]
    while session.step() is not None:
        checkpoints.append(session.checkpoint())
    assert len(checkpoints) >= 10
    for index, checkpoint in enumerate(checkpoints):
        recovered = sessions.restore_session(
            manifest,
            checkpoint,
            context=BackendContext(context.artifact_root, tmp_path / str(index)),
        )
        assert recovered.checkpoint() == checkpoint
        assert result_to_json(recovered.finish()) == expected


def test_observations_immutable_finish_cached_and_financial_identities(tmp_path):
    sessions, manifest, context = setup(tmp_path)
    session = sessions.open_session(manifest, context=context)
    initial = session.observe()
    with pytest.raises(TypeError):
        initial.account["cash"] = "0"
    with pytest.raises(TypeError):
        initial.account["holdings"]["A"] = "100"
    result = session.finish()
    assert session.finish() is result
    assert initial.account["cash"] == "10000.0"
    raw = json.loads((tmp_path / result.raw_result.uri).read_text())
    assert len(raw["fills"]) == 2
    assert sum(float(f["amount"]) for f in raw["capital_flow_ledger"]) == 50
    for f in raw["capital_flow_ledger"]:
        assert float(f["cash_after"]) - float(f["cash_before"]) == float(f["amount"])
    daily = raw["daily"][-1]
    assert float(daily["pnl"]) == pytest.approx(float(daily["nav"]) - 10000 - 50)
    # Minimum commission once per parent, impact inside price once, cash fees once.
    assert [float(f["transaction_cost"]) for f in raw["fills"]] == [5, 0]
    assert float(daily["cash"]) == pytest.approx(10000 - 2002 - 5 + 200 + 50)
    assert float(raw["daily"][1]["cash_receivable"]) == 200
    assert float(raw["daily"][1]["stock_receivable_value"]) == 900
    assert float(raw["holdings"][-1]["quantity"]) == 400
    assert float(daily["nav"]) == float(daily["cash"]) + float(daily["positions_value"])
    assert len(session.owner.simulation.daily) == 3
    session.finish()
    assert len(session.owner.simulation.daily) == 3
    with pytest.raises(ValueError):
        session.checkpoint()


class CountingPolicy:
    policy_id = "counting"
    version = "v1"
    state_schema = "counting.v1"

    def __init__(self, fail=False):
        self.count = 0
        self.fail = fail
        self.error = RuntimeError("original policy failure")

    def decide(self, observation):
        self.count += 1
        if self.fail:
            raise self.error
        return observation.account["proposed_weights"]

    def state(self):
        return {"count": self.count}

    def restore_state(self, state):
        self.count = state["count"]


def local_manifest(manifest):
    from quant_backtest_engine.product import manifest_to_json, parse_manifest

    wire = manifest_to_json(manifest)
    wire["policy"] = {
        "id": "counting",
        "version": "v1",
        "state_schema": "counting.v1",
        "config": {},
    }
    return parse_manifest(wire)


def test_local_policy_state_and_original_failure_checkpoint(tmp_path):
    sessions, manifest, context = setup(tmp_path)
    manifest = local_manifest(manifest)
    policy = CountingPolicy()
    session = sessions.open_session(manifest, context=context, policy=policy)
    session.step()
    checkpoint = session.checkpoint()
    restored_policy = CountingPolicy()
    restored = sessions.restore_session(
        manifest, checkpoint, context=context, policy=restored_policy
    )
    assert restored_policy.count == policy.count == 1
    assert restored.checkpoint() == checkpoint
    # Change only trusted policy behavior after the successful boundary.
    policy.fail = True
    while True:
        try:
            if session.step() is None:
                pytest.fail("expected another policy event")
        except RuntimeError as exc:
            assert exc is policy.error
            break
        checkpoint = session.checkpoint()
    assert session.last_successful_checkpoint == checkpoint
    # A poisoned owner must never be asked for another checkpoint.
    session.owner.checkpoint = lambda: pytest.fail("poisoned owner checkpoint invoked")
    for operation in (session.checkpoint, session.step, session.finish):
        with pytest.raises(RuntimeError) as failure:
            operation()
        assert failure.value is policy.error
    assert session.failure is policy.error
    recovered = sessions.restore_session(
        manifest, checkpoint, context=context, policy=CountingPolicy()
    )
    assert recovered.finish().status == "completed"


def test_normalization_unknown_remains_null():
    from quant_backtest_core.sessions.results import transport

    assert transport({"nav": float("nan"), "return_basis": None, "quantity": 0}) == {
        "nav": None,
        "return_basis": None,
        "quantity": "0",
    }


@pytest.mark.parametrize(
    "value, expected",
    [
        (0.00001, "0.00001"),
        (1e-8, "0.00000001"),
        (1e20, "100000000000000000000"),
        (-1e-8, "-0.00000001"),
        (0.0, "0.0"),
        (-0.0, "-0.0"),
        (1.2345678901234567e-20, "0.000000000000000000012345678901234567"),
    ],
)
def test_decimal_transport_scale_boundaries(value, expected):
    from quant_backtest_engine.product import EvidenceTable

    from quant_backtest_core.sessions.results import transport

    encoded = transport({"cash": value})
    assert encoded["cash"] == expected
    assert EvidenceTable("daily", "available", (encoded,), None).rows[0]["cash"] == expected
    assert float(encoded["cash"]).hex() == value.hex()


@pytest.mark.parametrize(
    "value",
    [
        float.fromhex("0x1.fffffffffffffp+1023"),
        float.fromhex("-0x1.fffffffffffffp+1023"),
        float.fromhex("0x1.0000000000000p-1022"),
        float.fromhex("0x0.0000000000001p-1022"),
        float.fromhex("-0x0.0000000000001p-1022"),
    ],
)
def test_extreme_finite_float_transport_roundtrips_without_zero_or_exponent(value):
    from quant_backtest_engine.product import EvidenceTable

    from quant_backtest_core.sessions.results import transport

    encoded = transport({"cash": value})
    assert "e" not in encoded["cash"].lower()
    assert float(encoded["cash"]).hex() == value.hex()
    assert EvidenceTable("daily", "available", (encoded,), None).rows[0]["cash"] == encoded["cash"]


def test_transport_unknown_and_nanosecond_clocks_remain_distinct():
    import pandas as pd

    from quant_backtest_core.sessions.results import transport

    assert transport(
        {"nan": float("nan"), "positive": float("inf"), "negative": float("-inf")}
    ) == {"nan": None, "positive": None, "negative": None}
    assert transport(pd.Timestamp(1767576720000000001, tz="UTC")) == "1767576720000000001"
