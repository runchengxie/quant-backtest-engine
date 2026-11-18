import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from quant_backtest_engine import EngineClient, EngineProtocolError
from quant_backtest_engine.depth import validate_request, validate_result
from quant_backtest_engine.product import loads_manifest

ROOT = Path(__file__).resolve().parents[2]


class DepthCodecTests(unittest.TestCase):
    def request(self):
        return json.loads((ROOT / "fixtures/depth.json").read_text())

    def result(self):
        return json.loads(
            (ROOT / "python/tests/fixtures/depth-result.json").read_text()
        )

    def test_native_hand_oracle_fixture(self):
        request = self.request()
        validate_request(request)
        result = validate_result(request, self.result())
        self.assertEqual(result["account"]["cash"], "9949.65")
        self.assertEqual(result["account"]["commission"], "0.05")
        self.assertEqual(
            [f["quantity"] for f in result["account"]["fills"]], ["2", "3"]
        )
        self.assertEqual(
            len({r["trade_id"] for r in result["receipts"] if r["kind"] == "filled"}), 2
        )

    def test_strict_request_rejects_malformed_events_and_commands(self):
        changes = [
            lambda r: r["events"][0].update(available_ns=r["events"][0]["ts_ns"] + 1),
            lambda r: r["events"][0].update(sequence=True),
            lambda r: r["events"][0].update(kind="order"),
            lambda r: r["events"][0]["asks"].append(r["events"][0]["asks"][0]),
            lambda r: r["events"][0]["bids"][0].update(price="11"),
            lambda r: r["commands"][0].update(
                information_ts_ns=r["events"][0]["ts_ns"]
            ),
            lambda r: r["commands"][0].update(quantity="0"),
            lambda r: r["commands"][0].update(limit_price="010.10"),
            lambda r: r.update(insert_latency_ns=-1),
            lambda r: r.update(required_capabilities=["unverified_queue_position"]),
            lambda r: r.update(end_ns=r["events"][0]["ts_ns"] + 60_000_000_001),
        ]
        for change in changes:
            request = self.request()
            change(request)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_request(request)

    def test_rejects_independently_corrupted_native_evidence(self):
        changes = [
            lambda r: r.update(request_sha256="0" * 64),
            lambda r: r["account"].update(cash="1"),
            lambda r: r["account"]["fills"][0].update(side="sell"),
            lambda r: r["account"]["fills"][0].update(price="11"),
            lambda r: r["account"]["fills"][0].update(commission="0"),
            lambda r: r["account"]["orders"][0].update(filled_quantity="6"),
            lambda r: r["decisions"][0].update(submitted_quantity="6"),
            lambda r: r["account"]["positions"][0].update(mark_price="100"),
            lambda r: r["receipts"].append(
                copy.deepcopy(next(e for e in r["receipts"] if e["kind"] == "filled"))
            ),
            lambda r: r.update(observation_ns=1),
            lambda r: r["account"].update(backend_version="other"),
            lambda r: r["decisions"][0].update(held_quantity="999"),
            lambda r: r["decisions"][0].update(free_cash="0"),
            lambda r: r["account"]["orders"][0].update(status="DENIED"),
            lambda r: r["receipts"][0].update(received_ns=1),
        ]
        for change in changes:
            result = self.result()
            change(result)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_result(self.request(), result)

    def test_client_snapshots_binary_and_rejects_false_results(self):
        with tempfile.TemporaryDirectory() as d:
            executable = Path(d) / "fake-engine"
            for output, valid in [
                (self.result(), True),
                ({"schema_version": "bad"}, False),
            ]:
                executable.write_text(
                    "#!/usr/bin/env python3\nprint(" + repr(json.dumps(output)) + ")\n"
                )
                executable.chmod(0o700)
                client = EngineClient(
                    executable, hashlib.sha256(executable.read_bytes()).hexdigest()
                )
                if valid:
                    self.assertEqual(client.run_depth(self.request()), output)
                else:
                    with self.assertRaises(EngineProtocolError):
                        client.run_depth(self.request())

    def test_manifest_profile_rejects_unknown_semantics(self):
        base = json.loads((ROOT / "fixtures/product/rust-depth.json").read_text())
        for change in [
            lambda r: r.update(share_basis="adjusted"),
            lambda r: r.update(timezone="UTC"),
            lambda r: r["settings"].update(extra=True),
            lambda r: r["tapes"]["events"][0].update(kind="unknown"),
        ]:
            wire = copy.deepcopy(base)
            change(wire)
            with self.assertRaises(ValueError):
                loads_manifest(json.dumps(wire))

    @unittest.skipUnless(
        os.environ.get("QUANT_ENGINE_BINARY"), "real native engine not configured"
    )
    def test_real_content_pinned_depth_client(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        self.assertEqual(client.depth_capabilities()["backend_version"], "0.66.0")
        result = client.run_depth(self.request())
        self.assertEqual(result["account"]["cash"], "9949.65")

    @unittest.skipUnless(
        os.environ.get("QUANT_ENGINE_BINARY"), "real native engine not configured"
    )
    def test_real_currency_rounding_at_sub_cent_prices(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        for price, fee, expected in [
            ("10.001", "0", "9990"),
            ("10.055", "1000", "9988.93"),
        ]:
            request = self.request()
            request["instrument"]["price_precision"] = 3
            request["fee_bps"] = fee
            request["events"][0]["asks"] = [{"price": price, "quantity": "1"}]
            request["commands"][0].update(quantity="1", limit_price=price)
            with self.subTest(price=price):
                self.assertEqual(client.run_depth(request)["account"]["cash"], expected)

    @unittest.skipUnless(
        os.environ.get("QUANT_ENGINE_BINARY"), "real native engine not configured"
    )
    def test_real_partial_cancel_and_target_feedback(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        request = self.request()
        first = request["events"][0]
        first["asks"] = [{"price": "10", "quantity": "2"}]
        request["events"] = [first]
        for seq, delta, price in [(2, 100, "10.20"), (3, 200, "10")]:
            event = copy.deepcopy(first)
            event.update(
                sequence=seq,
                ts_ns=first["ts_ns"] + delta,
                available_ns=first["ts_ns"] + delta,
            )
            event["asks"] = [{"price": price, "quantity": "10"}]
            request["events"].append(event)
        initial = request["commands"][0]
        initial.update(action="target", quantity="5", limit_price="10")
        cancel = copy.deepcopy(initial)
        cancel.update(
            id="cancel",
            event_sequence=2,
            action="cancel",
            quantity="0",
            limit_price="0",
            cancel_id=initial["id"],
        )
        target = copy.deepcopy(initial)
        target.update(id="next", event_sequence=3)
        request["commands"] = [initial, cancel, target]
        result = client.run_depth(request)
        self.assertEqual(result["decisions"][2]["held_quantity"], "2")
        self.assertEqual(result["decisions"][2]["submitted_quantity"], "3")
        self.assertEqual(result["account"]["positions"][0]["quantity"], "5")

    @unittest.skipUnless(
        os.environ.get("QUANT_ENGINE_BINARY"), "real native engine not configured"
    )
    def test_cancel_can_arrive_before_original_order(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        client = EngineClient(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
        request = self.request()
        request["insert_latency_ns"] = 100
        first = request["events"][0]
        event = copy.deepcopy(first)
        event.update(
            sequence=2, ts_ns=first["ts_ns"] + 50, available_ns=first["ts_ns"] + 50
        )
        request["events"].append(event)
        cancel = copy.deepcopy(request["commands"][0])
        cancel.update(
            id="cancel",
            action="cancel",
            quantity="0",
            limit_price="0",
            cancel_id=request["commands"][0]["id"],
            event_sequence=2,
        )
        request["commands"].append(cancel)
        result = client.run_depth(request)
        self.assertTrue(
            any(
                r["kind"] == "cancel_rejected" and r["ts_ns"] == event["ts_ns"]
                for r in result["receipts"]
            )
        )
        self.assertEqual(result["account"]["positions"][0]["quantity"], "5")


if __name__ == "__main__":
    unittest.main()
