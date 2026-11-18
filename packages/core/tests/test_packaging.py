import importlib.metadata
import json
import subprocess
import sys
import unittest


class PackagingTests(unittest.TestCase):
    def test_base_import_is_stdlib_and_sdk_only(self):
        code = "import quant_backtest_core,sys,json; print(json.dumps(sorted(sys.modules)))"
        modules = json.loads(
            subprocess.check_output([sys.executable, "-I", "-B", "-c", code], text=True)
        )
        for name in (
            "pandas",
            "numpy",
            "scipy",
            "torch",
            "qlib",
            "osqp",
            "quant_platform",
            "backtest_runtime",
        ):
            self.assertFalse(any(m == name or m.startswith(name + ".") for m in modules), name)

    def test_sdk_never_imports_core(self):
        code = "import quant_backtest_engine.product,sys; assert not any(m.startswith('quant_backtest_core') for m in sys.modules)"
        subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True)

    def test_namespace_and_distribution_version(self):
        dist = importlib.metadata.distribution("quant-backtest-core")
        self.assertEqual(dist.version, "0.3.0")
        for file in dist.files:
            if str(file).endswith(".py"):
                self.assertTrue(str(file).startswith("quant_backtest_core/"), str(file))
        requirements = dist.requires
        self.assertTrue(any("quant-backtest-engine-client" in r for r in requirements))
        self.assertFalse(
            any(name in " ".join(requirements).lower() for name in ("torch", "qlib", "osqp"))
        )

    def test_capabilities_cli_without_executable(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "quant_backtest_core.cli",
                "capabilities",
                "rust.nautilus.sessions",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        descriptor = json.loads(result.stdout)
        self.assertEqual(descriptor["checkpoint_schemas"], [])
        self.assertEqual(descriptor["identity"]["backend_id"], "rust.nautilus.sessions")


if __name__ == "__main__":
    unittest.main()
