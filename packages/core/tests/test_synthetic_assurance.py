"""Run reproducible, independent synthetic oracles through real native execution."""

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "synthetic_assurance", ROOT / "scripts/verify/synthetic_assurance.py"
)
module = importlib.util.module_from_spec(spec)


def load():
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("seed", [7, 19, 41])
def test_independent_finite_and_impact_oracles(seed):
    m = load()
    assert m.inventory_checks(seed, 24)["cases"] == 24
    assert m.impact_checks(seed, 24)["cases"] == 24


@pytest.mark.skipif(not os.environ.get("QUANT_ENGINE_BINARY"), reason="real engine not configured")
@pytest.mark.parametrize("seed", [7, 19, 41])
def test_native_parity_feedback_and_capital_stress(seed):
    m = load()
    client = m.client_for(Path(os.environ["QUANT_ENGINE_BINARY"]))
    assert m.native_lot_checks(client, seed, 32)["cases"] == 32
    assert m.account_checks(client, seed, 24)["decisions"] == 288
    feedback = m.feedback_check(client)
    assert feedback["first_holdings"] == "4" and feedback["second_quantity"] == "6"
    scenarios = m.capital_stress(client)
    assert len(scenarios) == 12
    assert {r["capital"] for r in scenarios} == {"20000000", "50000000"}
    assert any(r["filled"] == "0" for r in scenarios)


def test_path_reproducibility_and_independent_accounts():
    report = load().path_checks(7)
    assert report["paths"] == 8
    assert report["training_future_ignored"] and report["batch_order_invariant"]
