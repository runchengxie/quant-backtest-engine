"""Workspace paths preserve historical sources while using current package roots."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class LayoutTests(unittest.TestCase):
    def helper(self):
        spec=importlib.util.spec_from_file_location('workspace',ROOT/'scripts/workspace.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def test_declared_roots_and_historical_exporter_bytes(self):
        m=self.helper()
        for name in ['apps/docs/package.json','packages/engine/Cargo.toml','packages/core/pyproject.toml','packages/python-sdk/pyproject.toml','packages/microstructure-native/pyproject.toml','tests/fixtures/depth.json']:
            self.assertTrue((ROOT/name).is_file(),name)
        fixture=json.loads((ROOT/'docs/assets/method/fixtures.json').read_text())
        import hashlib
        sources=fixture['exporter_sources']|{'project_tools/export_method_fixtures.py':fixture['exporter_sha256']}
        for name,digest in sources.items():self.assertEqual(hashlib.sha256(m.source_path(ROOT,name).read_bytes()).hexdigest(),digest)
    def test_rejects_source_escape_and_symlinks(self):
        m=self.helper()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'workspace-layout.json').write_text(json.dumps({'schema':'engine-workspace-layout.v1','paths':{'old.py':'../outside.py'}}))
            (root/'link').symlink_to(root.parent/'outside.py')
            for name in ['../outside','/etc/passwd','old.py','link']:
                with self.assertRaises(ValueError):m.source_path(root,name)
    def test_stage_retains_exact_legacy_paths(self):
        spec=importlib.util.spec_from_file_location('reproduce',ROOT/'scripts/build/reproduce_method_fixtures.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'stage';module.stage_sources(ROOT,root)
            for name in ['method_market_cases.py','export_method_fixtures.py']:
                self.assertEqual((root/'project_tools'/name).read_bytes(),(ROOT/'scripts/build'/name).read_bytes())
            self.assertEqual((root/'fixtures/roundtrip.json').read_bytes(),(ROOT/'tests/fixtures/roundtrip.json').read_bytes())
