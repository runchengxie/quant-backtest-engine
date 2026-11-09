"""Installed product boundaries: no financial call after a rejected request."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quant_backtest_engine.product import loads_manifest, parse_manifest, result_to_json

from quant_backtest_core import BackendContext, run_manifest
from quant_backtest_core.backends.registry import get_backend
from quant_backtest_core.errors import ProductError

ROOT = Path(__file__).resolve().parents[2]


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.artifacts = self.base / "inputs"
        self.artifacts.mkdir()
        self.outputs = self.base / "outputs"
        self.wire = json.loads((ROOT / "fixtures/product/rust-session.json").read_text())
        (self.artifacts / "synthetic-calendar.json").write_bytes(
            (ROOT / "fixtures/product/synthetic-calendar.json").read_bytes()
        )
        self.binary = self.base / "engine"
        self.binary.write_bytes(b"unexecuted test artifact")
        self.context = BackendContext(
            self.artifacts,
            self.outputs,
            self.binary,
            hashlib.sha256(self.binary.read_bytes()).hexdigest(),
        )

    def rejected(self, wire=None, context=None):
        with patch("quant_backtest_core.backends.rust.EngineClient.run_sessions") as execute:
            with self.assertRaises((ProductError, ValueError)):
                run_manifest(parse_manifest(wire or self.wire), context=context or self.context)
            execute.assert_not_called()

    def test_unknown_backend_and_unavailable_optional_backends(self):
        for backend in ("arbitrary.import", "python.minute", "python.daily"):
            with self.subTest(backend=backend):
                wire = copy.deepcopy(self.wire)
                wire["backend_id"] = backend
                self.rejected(wire)

    def test_rust_rejects_action_restore_and_other_semantics(self):
        for capability in ("corporate_actions", "restore", "checkpoint"):
            wire = copy.deepcopy(self.wire)
            wire["required_capabilities"].append(capability)
            self.rejected(wire)
        for key, value in (
            ("model_versions", {"custom": "1"}),
            ("share_basis", "adjusted"),
            ("timezone", "UTC"),
            ("input_schema", "future.v9"),
            ("policy", {"id": "custom", "version": "1", "state_schema": "v1", "config": {}}),
        ):
            wire = copy.deepcopy(self.wire)
            wire[key] = value
            self.rejected(wire)

    def test_missing_binary_and_wrong_digest(self):
        self.rejected(context=BackendContext(self.artifacts, self.outputs, None, None))
        self.rejected(context=BackendContext(self.artifacts, self.outputs, self.binary, "0" * 64))

    def test_traversal_remote_and_symlink_artifacts(self):
        outside = self.base / "outside.json"
        outside.write_text("{}")
        (self.artifacts / "escape.json").symlink_to(outside)
        for uri in ("../outside.json", str(outside), "https://example.com/a", "escape.json"):
            wire = copy.deepcopy(self.wire)
            wire["calendar"]["uri"] = uri
            self.rejected(wire)

    def test_digest_mismatch_is_exact_bytes(self):
        with (self.artifacts / "synthetic-calendar.json").open("ab") as target:
            target.write(b" ")
        self.rejected()

    def test_artifact_profile_and_native_validation_before_execution(self):
        for sessions in ([{"open_ts_ns": 2}], [], copy.deepcopy(self.wire["tapes"]["sessions"])):
            if sessions and "session_date" in sessions[0]:
                sessions[0]["quotes"][-1]["bid"] = "99"
            payload = json.dumps(sessions).encode()
            (self.artifacts / "sessions.json").write_bytes(payload)
            wire = copy.deepcopy(self.wire)
            wire["tapes"]["sessions"] = {
                "uri": "sessions.json",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "media_type": "application/json",
            }
            self.rejected(wire)

    def test_output_input_collision_and_traversal_rejected(self):
        wire = copy.deepcopy(self.wire)
        wire["output_uri"] = "synthetic-calendar.json"
        self.rejected(
            wire,
            BackendContext(self.artifacts, self.artifacts, self.binary, self.context.rust_sha256),
        )
        for uri in ("../escape.json", "/tmp/result.json", "https://example.com/result"):
            wire = copy.deepcopy(self.wire)
            wire["output_uri"] = uri
            self.rejected(wire)

    def test_existing_output_is_never_overwritten(self):
        self.outputs.mkdir()
        output = self.outputs / self.wire["output_uri"]
        output.write_text("retain me")
        self.rejected()
        self.assertEqual(output.read_text(), "retain me")

    def test_output_parent_file_rejected_before_execution(self):
        self.outputs.mkdir()
        (self.outputs / "blocked").write_text("existing input")
        wire = copy.deepcopy(self.wire)
        wire["output_uri"] = "blocked/result.json"
        native = json.loads((ROOT / "python/tests/fixtures/session-result.json").read_text())
        with patch(
            "quant_backtest_core.backends.rust.EngineClient.run_sessions", return_value=native
        ) as execute:
            with self.assertRaises((ValueError, OSError)):
                run_manifest(parse_manifest(wire), context=self.context)
            execute.assert_not_called()

    def test_native_semantic_preflight_matrix(self):
        mutations = [
            lambda w: w["initial_account"].update(cash="0"),
            lambda w: w["settings"].update(fee_bps="10001"),
            lambda w: w["inline_inputs"]["instruments"][0].update(symbol="BAD.SYMBOL"),
            lambda w: w["tapes"]["sessions"][0]["quotes"][0].update(symbol="UNKNOWN"),
            lambda w: w["tapes"]["sessions"][0]["quotes"][0].update(bid_size="1.1"),
            lambda w: w["tapes"]["sessions"][0]["quotes"][0].update(ask="0"),
            lambda w: w["tapes"]["sessions"][0]["quotes"][0].update(bid="1.001"),
            lambda w: w["tapes"]["sessions"][0]["orders"][0].update(quantity="0"),
            lambda w: w["tapes"]["sessions"][0]["orders"][0].update(information_ts_ns="0"),
            lambda w: w["tapes"]["sessions"][1]["orders"][0].update(id="buy"),
            lambda w: w["tapes"]["sessions"][1]["orders"][0].update(information_ts_ns="1"),
            lambda w: w["tapes"]["sessions"][0]["quotes"].pop(),
            lambda w: w["tapes"]["sessions"][0].update(open_ts_ns="1735781400000000001"),
        ]
        for mutate in mutations:
            wire = copy.deepcopy(self.wire)
            mutate(wire)
            self.rejected(wire)

    def test_loaded_duplicate_json_and_numeric_clock_rejected(self):
        for payload in (
            b'{"symbol":"AAA","symbol":"BBB"}',
            b"[NaN]",
            json.dumps([{"open_ts_ns": 1760000000000000001}]).encode(),
        ):
            (self.artifacts / "bad.json").write_bytes(payload)
            wire = copy.deepcopy(self.wire)
            wire["tapes"]["sessions"] = {
                "uri": "bad.json",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "media_type": "application/json",
            }
            self.rejected(wire)

    def test_descriptor_is_native_only(self):
        descriptor = get_backend("rust.nautilus.sessions", self.context).descriptor()
        self.assertEqual(descriptor.checkpoint_schemas, ())
        self.assertEqual(
            set(descriptor.capabilities),
            {
                "session_ledger",
                "configured_t_plus_one",
                "buy_lots",
                "quote_trade_permissions",
                "quote_liquidity",
            },
        )
        self.assertIsNone(descriptor.identity.source_revision)
        self.assertRegex(descriptor.identity.source_sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(descriptor.identity.artifact_sha256, self.context.rust_sha256)

    def test_native_payload_exact_and_raw_object_preserved(self):
        native = json.loads((ROOT / "python/tests/fixtures/session-result.json").read_text())
        with patch(
            "quant_backtest_core.backends.rust.EngineClient.run_sessions", return_value=native
        ) as execute:
            result = run_manifest(parse_manifest(self.wire), context=self.context)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(
            execute.call_args.args[0], json.loads((ROOT / "fixtures/sessions.json").read_text())
        )
        raw = (self.outputs / result.raw_result.uri).read_bytes()
        self.assertEqual(json.loads(raw), native)
        self.assertEqual(result.normalization.source_sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.raw_result.sha256, result.normalization.source_sha256)
        self.assertEqual(result.summary["final_nav"], "10197.8")
        tables = {t.name: t for t in result.tables}
        self.assertEqual(tables["rights"].status, "unavailable")
        self.assertEqual(tables["cash"].status, "unavailable")
        self.assertEqual(tables["fills"].rows[0]["ts_ns"], "1735781400000000000")
        self.assertEqual(
            json.loads((self.outputs / self.wire["output_uri"]).read_text()), result_to_json(result)
        )

    def test_native_failure_propagates_without_fallback(self):
        from quant_backtest_engine import EngineProtocolError

        with patch(
            "quant_backtest_core.backends.rust.EngineClient.run_sessions",
            side_effect=EngineProtocolError("original failure"),
        ) as execute:
            with self.assertRaisesRegex(EngineProtocolError, "original failure"):
                run_manifest(loads_manifest(json.dumps(self.wire)), context=self.context)
            self.assertEqual(execute.call_count, 1)
        self.assertFalse((self.outputs / self.wire["output_uri"]).exists())


if __name__ == "__main__":
    unittest.main()
