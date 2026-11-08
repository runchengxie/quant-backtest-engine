"""Hand expectations, publication contract and optional real-owner parity."""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "docs/assets/method/fixtures.json"


class MethodFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ASSET.exists(), "owner-generated public fixtures are missing")
        self.data = json.loads(ASSET.read_text())

    def scenario(self, scene, scenario=0):
        return self.data["scenes"][scene]["scenarios"][scenario]

    def test_schema_provenance_and_complete_scenes(self):
        self.assertEqual(self.data["schema"], "engine-method-replay.v1")
        self.assertEqual(len(self.data["scenes"]), 8)
        self.assertEqual(
            self.data["owners"]["platform"]["revision"],
            "7a618bddd8fdeee5dbe37fe5b54a9698e0de5355",
        )
        self.assertEqual(
            self.data["owners"]["runtime"]["revision"],
            "01ed4c34f955ef6cd39d13aa073b6d61b610d321",
        )
        self.assertEqual(
            self.data["exporter_sha256"],
            hashlib.sha256(
                (ROOT / "project_tools/export_method_fixtures.py").read_bytes()
            ).hexdigest(),
        )
        for source, expected in self.data["exporter_sources"].items():
            self.assertEqual(
                hashlib.sha256((ROOT / source).read_bytes()).hexdigest(), expected
            )
        for scene in self.data["scenes"].values():
            self.assertIn("supported_controls", scene)
            self.assertEqual(
                scene["supported_controls"]["scenario_ids"],
                [case["id"] for case in scene["scenarios"]],
            )
            for scenario in scene["scenarios"]:
                self.assertTrue(scenario["states"])
                self.assertTrue(scenario.get("status"))
                self.assertTrue(scenario.get("evidence_boundary"))
                canonical = json.dumps(
                    scenario["inputs"], sort_keys=True, allow_nan=False
                ).encode()
                self.assertEqual(
                    scenario["input_sha256"], hashlib.sha256(canonical).hexdigest()
                )
                self.assertEqual(scenario["config_sha256"], scenario["input_sha256"])
                self.assertTrue(scenario["units"])
                self.assertTrue(scenario["clocks"])
                self.assertTrue(scenario["owner"])
                self.assertEqual(scenario["evidence"], "synthetic")
                self.assertTrue(scenario["source"])
        wire = ASSET.read_text()
        for forbidden in [
            "/home/",
            "/run/media/",
            "quant-research",
            "w085",
            "account_id",
        ]:
            self.assertNotIn(forbidden, wire)

    def test_transient_decay_and_separate_nondecaying_assumption(self):
        first = self.scenario("impact")["states"]
        self.assertAlmostEqual(float(first[0]["offset"]), 0.1)
        self.assertAlmostEqual(float(first[0]["transient"]), 0.2)
        self.assertAlmostEqual(float(first[1]["transient"]), 0.2 / math.e)
        self.assertEqual(first[1]["permanent"], "0")
        stress = self.scenario("impact", 2)["states"]
        self.assertAlmostEqual(float(stress[1]["permanent"]), 0.1)

    def test_engine_accounting_and_single_cash_debit(self):
        last = self.scenario("flow")["states"][-1]
        self.assertEqual(last["cash"], "10019.78")
        self.assertEqual(last["fees"], "0.22")
        cost = self.scenario("cost")["states"][-1]
        self.assertEqual(cost["cash"], "10989")
        self.assertEqual(cost["gross"], "1010")
        self.assertEqual(cost["fees"], "1")
        self.assertEqual(cost["impact_cost"], "10")

    def test_book_walk_and_partial_report_clock(self):
        rows = self.scenario("book")["states"]
        self.assertEqual([r["quantity"] for r in rows], ["0", "5", "15", "15"])
        self.assertEqual(rows[-1]["remaining"], "5")
        self.assertEqual(rows[2]["reported"], "0")
        self.assertEqual(rows[3]["reported"], "15")

    def test_discrete_feasible_grid_and_fee_discontinuity(self):
        a, b = [s["states"][-1] for s in self.data["scenes"]["lots"]["scenarios"][:2]]
        self.assertEqual(a["shares"], "1,2")
        self.assertEqual(b["shares"], "1,1")
        self.assertEqual(b["cash"], "2")
        grid = self.scenario("lots", 2)["grid"]
        self.assertEqual(len(grid), 16)
        self.assertEqual(sum(row["feasible"] for row in grid), 7)

    def test_independent_execution_market_paths_and_feedback(self):
        scenarios = self.data["scenes"]["paths"]["scenarios"]
        a, b, c = scenarios[:3]
        self.assertEqual(a["forecast_sha256"], b["forecast_sha256"])
        self.assertEqual(a["market_sha256"], b["market_sha256"])
        self.assertNotEqual(a["states"][-1]["quantity"], b["states"][-1]["quantity"])
        self.assertNotEqual(a["market_sha256"], c["market_sha256"])
        self.assertNotEqual(a["states"][-1]["cash"], c["states"][-1]["cash"])
        hold = scenarios[3]["states"]
        self.assertEqual(hold[-1]["quantity"], "100")
        self.assertEqual(hold[-1]["next_target"], "0.1")

    def test_null_selection_retains_all_attempts(self):
        rows = self.scenario("selection")["states"]
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(r["selected"] for r in rows), 1)
        scores = [float(r["score"]) for r in rows]
        self.assertAlmostEqual(sum(scores), 0)
        self.assertGreater(max(scores), 0)
        self.assertLess(min(scores), 0)

    def test_recovery_shared_budget_and_unfinished_exit(self):
        scenes = self.data["scenes"]["risk"]["scenarios"]
        recovery = scenes[0]
        self.assertEqual(recovery["uninterrupted_sha256"], recovery["recovered_sha256"])
        shared = scenes[1]["states"][-1]
        self.assertEqual(shared["quantity"], "100")
        self.assertEqual(shared["cash"], "10989")
        self.assertEqual(shared["fees"], "1")
        residual = scenes[2]["states"][-1]
        self.assertEqual(residual["quantity"], "400")
        self.assertEqual(residual["cash"], "6000")
        self.assertEqual(residual["wealth"], "10000")
        self.assertIsNone(residual["cash_realized_wealth"])

    def test_action_rights_release_and_external_capital(self):
        scenarios = self.data["scenes"]["risk"]["scenarios"]
        self.assertGreaterEqual(
            len(scenarios), 4, "action and capital states are missing"
        )
        states = scenarios[3]["states"]
        ex = next(row for row in states if row["phase"] == "ex")
        self.assertEqual(ex["cash_right"], "200")
        self.assertEqual(ex["stock_right"], "200")
        self.assertEqual(ex["wealth"], "10000")
        release = next(row for row in states if row["phase"] == "release")
        self.assertEqual(release["cash"], "8200")
        self.assertEqual(release["quantity"], "400")
        flow = states[-1]
        self.assertEqual(flow["wealth_before_flow"], "9400")
        self.assertEqual(flow["capital_flow"], "1000")
        self.assertEqual(flow["wealth"], "10400")

    def test_risk_forecast_realization_and_missing_evidence(self):
        scenarios = self.data["scenes"]["risk"]["scenarios"]
        self.assertGreaterEqual(
            len(scenarios), 6, "matched-horizon risk audit is missing"
        )
        full = scenarios[4]["states"][-1]
        self.assertEqual(full["predicted_variance"], "2.5")
        self.assertEqual(full["realized_squared_residual"], "12.5")
        self.assertEqual(full["variance_ratio"], "5")
        missing = scenarios[5]["states"][-1]
        self.assertEqual(missing["coverage"], "0")
        self.assertIsNone(missing["realized_squared_residual"])
        self.assertFalse(scenarios[4]["certified"])
        self.assertEqual(scenarios[4]["real_calibration"], "unavailable")

    @unittest.skipUnless(
        os.environ.get("METHOD_OWNER_PARITY"), "optional owner environment required"
    )
    def test_actual_owner_reexport_byte_parity(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fixtures.json"
            subprocess.run(
                [
                    os.environ.get("METHOD_PYTHON", "python3"),
                    str(ROOT / "project_tools/export_method_fixtures.py"),
                    "--platform",
                    os.environ["METHOD_PLATFORM"],
                    "--runtime",
                    os.environ["METHOD_RUNTIME"],
                    "--engine",
                    os.environ["QUANT_ENGINE_BINARY"],
                    "--output",
                    str(output),
                ],
                check=True,
            )
            self.assertEqual(output.read_bytes(), ASSET.read_bytes())


if __name__ == "__main__":
    unittest.main()
