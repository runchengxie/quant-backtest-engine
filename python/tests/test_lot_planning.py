"""Independent protocol and real-executable acceptance for native lot planning."""

import hashlib
import json
import os
import unittest
from pathlib import Path

from quant_backtest_engine import EngineClient
from quant_backtest_engine.lot_planning import validate_request, validate_result

ROOT = Path(__file__).resolve().parents[2]


class LotPlanningTests(unittest.TestCase):
    def request(self):
        return json.loads((ROOT / "fixtures/lot-planning.json").read_text())

    def test_invalid_bounded_domain(self):
        for update in (
            {"max_states": True},
            {"prices": ["0.00001", "4"]},
            {"max_lots": [2**64, 3]},
            {"lot_sizes": [0, 1]},
            {"cash_budget": "-1"},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_request(self.request() | update)

    @unittest.skipUnless(
        os.environ.get("QUANT_ENGINE_BINARY"), "real engine not configured"
    )
    def test_real_hand_oracle_and_corrupt_evidence(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        request = self.request()
        result = client.plan_lots(request)
        self.assertEqual(result["quantities"], [1, 1])
        self.assertEqual(result["candidate_gap"], "2")
        for update in (
            {"spent": "0"},
            {"quantities": [2, 1]},
            {"evaluated": 1},
            {"request_sha256": "0" * 64},
            {"candidate_gap": "0"},
            {"status": "search_limit"},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_result(request, result | update)
        limited = client.plan_lots(request | {"max_states": 1})
        self.assertEqual(limited["status"], "search_limit")
        self.assertIsNone(limited["quantities"])

    @unittest.skipUnless(
        os.environ.get("QUANT_ENGINE_BINARY"), "real engine not configured"
    )
    def test_suboptimal_and_nonlexicographic_claims_are_rejected(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        request = self.request() | {"candidate_quantities": None}
        result = client.plan_lots(request)
        with self.assertRaises(ValueError):
            validate_result(
                request,
                result | {"quantities": [0, 0], "spent": "0", "objective": "4.5"},
            )
        request = request | {
            "prices": ["1"],
            "target_quantities": ["0.5"],
            "max_lots": [1],
            "lot_sizes": [1],
            "cash_budget": "10",
            "minimum_commission": "0",
        }
        result = client.plan_lots(request)
        with self.assertRaises(ValueError):
            validate_result(
                request, result | {"quantities": [1], "spent": "1", "objective": "0.25"}
            )

    @unittest.skipUnless(
        os.environ.get("QUANT_ENGINE_BINARY"), "real engine not configured"
    )
    def test_precision_and_full_search_budget_boundaries(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        request = self.request() | {
            "prices": ["1"] * 16,
            "target_quantities": ["999999999.9999"] * 16,
            "max_lots": [0] * 16,
            "lot_sizes": [1] * 16,
            "candidate_quantities": None,
        }
        self.assertEqual(
            client.plan_lots(request)["objective"], "15999999999996800000.00000016"
        )
        request = request | {
            "prices": ["1"],
            "target_quantities": ["50000.5"],
            "max_lots": [99999],
            "lot_sizes": [1],
            "cash_budget": "1000000",
            "minimum_commission": "0",
        }
        self.assertEqual(client.plan_lots(request)["quantities"], [50000])
