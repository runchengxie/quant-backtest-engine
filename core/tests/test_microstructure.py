"""Standalone simulator ownership and contract boundaries."""

import importlib.abc
import sys

import pytest

from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure.ordering import sort_simulator_events
from quant_backtest_core.microstructure.pack import SimulatorEvent


def test_explicit_missing_native_rejects_without_fallback(monkeypatch):
    class AbsentNative(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "_microstructure_rs":
                raise ModuleNotFoundError("explicitly absent _microstructure_rs")

    monkeypatch.delitem(sys.modules, "_microstructure_rs", raising=False)
    monkeypatch.setattr(sys, "meta_path", [AbsentNative(), *sys.meta_path])
    with pytest.raises(ModuleNotFoundError, match="_microstructure_rs"):
        MatchingEngine(backend="rust")
    with pytest.raises(ModuleNotFoundError, match="_microstructure_rs"):
        sort_simulator_events([], backend="rust")


def test_equal_clock_sequence_and_source_ties_are_stable():
    events = [
        SimulatorEvent(2**53 + 1, "order", order_id=name, channel="A", sequence=7, source_index=0)
        for name in ["first", "second", "third"]
    ]
    assert [e.order_id for e in sort_simulator_events(events)] == ["first", "second", "third"]


def test_duplicate_identifier_preserves_original_cancel_semantics():
    engine = MatchingEngine()
    engine.apply_order("same", 1, 100, 5)
    engine.apply_order("same", 1, 100, 7)
    assert engine.lob.best_bid() == (100, 12)
    assert engine.cancel_order("same", 3)
    assert engine.lob.best_bid() == (100, 9)
    assert engine.cancel_order("same")
    assert engine.lob.best_bid() is None


def test_matching_without_ticknet_or_torch_installed():
    import subprocess

    code = """
import importlib.abc, sys
class NoTraining(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'ticknet', 'quant_platform', 'backtest_runtime'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, NoTraining())
from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure import pack, replay, ordering, correctness
book = MatchingEngine()
book.apply_order('b', 1, 100, 10)
assert book.lob.best_bid() == (100, 10)
assert not any(n.split('.')[0] in {'torch', 'ticknet', 'quant_platform'} for n in sys.modules)
"""
    subprocess.run([sys.executable, "-I", "-c", code], check=True)
