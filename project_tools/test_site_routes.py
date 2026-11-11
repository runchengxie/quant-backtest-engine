import tempfile
import unittest
from pathlib import Path
from project_tools.inventory_site_routes import inventory_site_routes


class SiteRoutesTests(unittest.TestCase):
    def test_preserves_actual_legacy_routes_and_fragments(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "index.html").write_text(
                '<h1 id="_1">标题</h1><select id="method-risk-scenario"></select><a href="#_1">Go</a>'
            )
            result = inventory_site_routes(p)
            self.assertEqual(
                result["html"]["index.html"]["ids"], ["_1", "method-risk-scenario"]
            )
            self.assertEqual(
                result["html"]["index.html"]["control_ids"], ["method-risk-scenario"]
            )
            self.assertEqual(result["html"]["index.html"]["hrefs"], ["#_1"])

    def test_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "bad").symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                inventory_site_routes(p)
