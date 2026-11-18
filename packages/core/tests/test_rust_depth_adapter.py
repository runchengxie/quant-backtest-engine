"""Real executable product acceptance; synthetic data and isolated outputs only."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from quant_backtest_engine.product import ArtifactRef, loads_manifest

from quant_backtest_core import BackendContext, run_manifest
from quant_backtest_core.backends.registry import get_backend
from quant_backtest_core.errors import ProductError

ROOT = Path(__file__).resolve().parents[3]


def test_depth_backend_requires_explicit_trusted_executable(tmp_path):
    manifest = loads_manifest((ROOT / "tests/fixtures/product/rust-depth.json").read_text())
    context = BackendContext(ROOT / "tests/fixtures/product", tmp_path)
    backend = get_backend("rust.nautilus.depth", context)
    assert backend.descriptor().identity.backend_id == "rust.nautilus.depth"
    with pytest.raises(ProductError, match="executable"):
        backend.validate(manifest, context)


@pytest.mark.skipif(
    not os.environ.get("QUANT_ENGINE_BINARY"), reason="real native engine not configured"
)
def test_real_depth_product_preserves_owned_cash_and_evidence(tmp_path):
    binary = Path(os.environ["QUANT_ENGINE_BINARY"])
    context = BackendContext(
        ROOT / "tests/fixtures/product",
        tmp_path,
        binary,
        hashlib.sha256(binary.read_bytes()).hexdigest(),
    )
    manifest = loads_manifest((ROOT / "tests/fixtures/product/rust-depth.json").read_text())
    result = run_manifest(manifest, context=context)
    assert result.status == "completed"
    assert result.summary["final_cash"] == "9949.65"
    assert result.summary["total_commission"] == "0.05"
    assert {t.name for t in result.tables if t.status == "available"} == {
        "fills",
        "positions",
        "reports",
    }
    raw = (tmp_path / result.raw_result.uri).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == result.raw_result.sha256
    assert json.loads(raw)["account"]["cash"] == "9949.65"
    assert len(json.loads(raw)["receipts"]) == 3
    with pytest.raises(ProductError):
        run_manifest(manifest, context=context)
    assert (tmp_path / result.raw_result.uri).read_bytes() == raw


@pytest.mark.skipif(
    not os.environ.get("QUANT_ENGINE_BINARY"), reason="real native engine not configured"
)
def test_depth_calendar_cannot_be_substituted(tmp_path):
    binary = Path(os.environ["QUANT_ENGINE_BINARY"])
    context = BackendContext(
        tmp_path, tmp_path / "out", binary, hashlib.sha256(binary.read_bytes()).hexdigest()
    )
    (tmp_path / "wrong.json").write_text("{}")
    manifest = loads_manifest((ROOT / "tests/fixtures/product/rust-depth.json").read_text())
    wrong = replace(
        manifest,
        calendar=ArtifactRef("wrong.json", hashlib.sha256(b"{}").hexdigest(), "application/json"),
    )
    with pytest.raises(ProductError, match="calendar"):
        run_manifest(wrong, context=context)
