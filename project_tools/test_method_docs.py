"""Full no-JS tables, semantic locales and local replay payload contract."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MethodDocs(unittest.TestCase):
    def test_complete_localized_no_js_tables(self):
        hook = ROOT / "project_tools/method_docs.py"
        self.assertTrue(hook.exists(), "complete no-JS rendering is missing")
        spec = importlib.util.spec_from_file_location("method_docs", hook)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixtures = json.loads((ROOT / "docs/assets/method/fixtures.json").read_text())
        for locale in ["en", "zh-CN"]:
            suffix = "" if locale == "en" else ".zh-CN"
            source = (ROOT / f"docs/backtesting-explained{suffix}.md").read_text()
            html = module.on_page_markdown(
                source,
                SimpleNamespace(
                    file=SimpleNamespace(src_uri=f"backtesting-explained{suffix}.md")
                ),
                None,
                None,
            )
            self.assertEqual(html.count('class="method-scene"'), 8)
            self.assertEqual(html.count('class="method-payload"'), 8)
            for scene in fixtures["scenes"].values():
                for scenario in scene["scenarios"]:
                    for index in range(len(scenario["states"])):
                        self.assertIn(
                            f'data-scenario="{scenario["id"]}" data-frame="{index}"',
                            html,
                        )
            self.assertIn("10019.78", html)
            self.assertIn("10989", html)
            self.assertNotIn("<!-- method:", html)
            self.assertIn('aria-live="polite"', html)
            self.assertIn('scope="col"', html)
            self.assertIn('method-controls" hidden', html)


if __name__ == "__main__":
    unittest.main()
