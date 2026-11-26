"""The registered panel cannot silently select a best-looking subset."""

import importlib.util
import sys
from pathlib import Path


def test_fixed_panel_identity_and_counts():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "export_control_followthrough", root / "scripts/verify/export_control_followthrough.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root / "scripts/verify"))
    spec.loader.exec_module(module)
    rows = module.fixed_studies()
    assert len(rows) == 70
    assert {p for p, _ in rows} == {"feedback", "price", "capacity"}
    assert len({module.study_id(c) for _, c in rows}) == 65
    assert {c.price_path for p, c in rows if p == "price"} == {
        "flat",
        "up",
        "down",
        "oscillating",
        "jump",
    }
