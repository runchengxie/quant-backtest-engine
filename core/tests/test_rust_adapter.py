import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from quant_backtest_engine.product import loads_manifest

from quant_backtest_core import BackendContext, run_manifest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("QUANT_ENGINE_BINARY"), "real executable not configured")
class RustAcceptanceTests(unittest.TestCase):
    def test_installed_session_adapter_oracle(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        with tempfile.TemporaryDirectory() as output:
            result = run_manifest(
                loads_manifest((ROOT / "fixtures/product/rust-session.json").read_text()),
                context=BackendContext(
                    ROOT / "fixtures/product",
                    Path(output),
                    binary,
                    hashlib.sha256(binary.read_bytes()).hexdigest(),
                ),
            )
            self.assertEqual(result.summary["final_cash"], "10197.8")
            self.assertEqual(result.summary["final_nav"], "10197.8")
            self.assertEqual(result.summary["total_commission"], "2.2")
            raw = json.loads((Path(output) / result.raw_result.uri).read_bytes())
            self.assertEqual(raw["backend_version"], "0.66.0")
            self.assertEqual(len(raw["fills"]), 2)

    def test_installed_cli_runs_real_engine(self):
        binary = Path(os.environ["QUANT_ENGINE_BINARY"])
        with tempfile.TemporaryDirectory() as output:
            command = [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "quant_backtest_core.cli",
                "run-manifest",
                str(ROOT / "fixtures/product/rust-session.json"),
                "--artifact-root",
                str(ROOT / "fixtures/product"),
                "--output-root",
                output,
                "--rust-executable",
                str(binary),
                "--rust-sha256",
                hashlib.sha256(binary.read_bytes()).hexdigest(),
            ]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result["summary"]["final_nav"], "10197.8")
            self.assertEqual(
                result, json.loads((Path(output) / "synthetic-result.json").read_text())
            )
            # Reusing the output name must fail without changing either artifact.
            before = (Path(output) / "synthetic-result.json").read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(second.stdout, "")
            self.assertEqual((Path(output) / "synthetic-result.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
