"""Bounded scenario integrity without executing financial logic in the browser."""

import json
import os
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.workspace import source_path
from decimal import Decimal
from pathlib import Path

from scripts.build.export_opportunity_example import (
    canonical,
    case_inputs,
    digest,
)

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "docs/assets/learning/opportunity.json"


class OpportunityExampleTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(ASSET.read_text())

    def test_owner_values_signed_and_recorded_fee_once(self):
        self.assertEqual(self.value["schema"], "engine-opportunity-example.v1")
        self.assertEqual([c["id"] for c in self.value["cases"]], ["down", "flat", "up"])
        for case, expected in zip(self.value["cases"], ["-200", "0", "200"]):
            row = case["outputs"]["parents"][0]
            self.assertEqual(Decimal(row["opportunity_shortfall"]), Decimal(expected))
            for name, number in [
                ("filled_shares", "100"),
                ("unfilled_shares", "100"),
                ("reference_price_shortfall", "10"),
                ("recorded_cash_fees", "5"),
                ("reference_shortfall_with_recorded_fees", "15"),
                ("modeled_cash_fees", "0"),
            ]:
                self.assertEqual(Decimal(row[name]), Decimal(number), name)
            self.assertFalse(row["attribution_additive"])
            self.assertEqual(row["fee_evidence"], "caller_recorded")
            self.assertEqual(case["outputs"]["real_calibration"], "unavailable")
            self.assertEqual(case["outputs"]["schema"], "transaction-cost-evidence.v1")

    def test_complete_inputs_and_clock_bounds(self):
        for case, benchmark in zip(self.value["cases"], ["8", "10", "12"]):
            self.assertEqual(case["inputs"], case_inputs(case["id"], benchmark))
            parent = case["inputs"]["parents"][0]
            fill = case["inputs"]["fills"][0]
            self.assertEqual(parent["requested_shares"], "200")
            self.assertEqual(fill["shares"], "100")
            self.assertEqual(fill["price"], "10.1")
            self.assertEqual(fill["recorded_commission"], "5")
            self.assertEqual(parent["source_binding"], fill["source_binding"])
            clocks = (
                [
                    parent[k]
                    for k in [
                        "reference_ns",
                        "reference_available_ns",
                        "decision_ns",
                        "arrival_ns",
                        "arrival_available_ns",
                    ]
                ]
                + [fill["fill_ns"], fill["receipt_ns"]]
                + [
                    parent[k]
                    for k in [
                        "completed_ns",
                        "opportunity_ns",
                        "opportunity_available_ns",
                        "available_ns",
                    ]
                ]
            )
            self.assertEqual(clocks, sorted(clocks))
            for clock in clocks:
                self.assertIsInstance(clock, str)
                self.assertGreaterEqual(int(clock), 1798761600000000000)
                self.assertLess(int(clock), 1798848000000000000)

    def test_receipt_exporter_source_and_registered_wheel(self):
        payload = {k: v for k, v in self.value.items() if k != "receipt"}
        self.assertEqual(
            self.value["receipt"]["payload_sha256"], digest(canonical(payload))
        )
        p = self.value["provenance"]
        lock_path = ROOT / "docs/assets/method/owner-lock.json"
        lock = json.loads(lock_path.read_text())
        self.assertEqual(p["owner_lock_sha256"], digest(lock_path.read_bytes()))
        self.assertEqual(p["provider_revision"], lock["provider_revisions"]["core"])
        self.assertEqual(p["wheel"]["sha256"], lock["wheels"][p["wheel"]["name"]])
        self.assertEqual(
            p["exporter"]["sha256"], digest(source_path(ROOT, p["exporter"]["path"]).read_bytes())
        )
        source = subprocess.check_output(
            ["git", "show", p["provider_revision"] + ":" + p["source"]["path"]],
            cwd=ROOT,
        )
        self.assertEqual(p["source"]["sha256"], digest(source))
        self.assertEqual(p["dependencies"], lock["dependencies"])

        def no_floats(value):
            self.assertNotIsInstance(value, float)
            if isinstance(value, dict):
                for item in value.values():
                    no_floats(item)
            elif isinstance(value, list):
                for item in value:
                    no_floats(item)

        no_floats(self.value)

    @unittest.skipUnless(
        os.environ.get("OPPORTUNITY_OWNER_PYTHON"),
        "optional exact installed owner environment",
    )
    def test_exact_installed_owner_reproduces_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "opportunity.json"
            subprocess.run(
                [
                    os.environ["OPPORTUNITY_OWNER_PYTHON"],
                    str(ROOT / "scripts/build/export_opportunity_example.py"),
                    "--output",
                    str(target),
                ],
                cwd=ROOT,
                check=True,
            )
            self.assertEqual(target.read_bytes(), ASSET.read_bytes())
