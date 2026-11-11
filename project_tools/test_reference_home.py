import tempfile
import unittest
from pathlib import Path
from project_tools.extract_reference_home import extract_reference_home


class ReferenceHomeTests(unittest.TestCase):
    def test_extracts_current_home_not_stale_blob(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            site = p / "site"
            site.mkdir()
            (site / "index.zh-CN").mkdir()
            for f in [site / "index.html", site / "index.zh-CN/index.html"]:
                f.write_text(
                    '<nav>discard</nav><article class="md-content__inner"><a class="md-content__button">edit</a><h1 id="_1">fresh</h1><br/><h2 id="more">more</h2><script>bad()</script></article>'
                )
            result = extract_reference_home(site, p / "out")
            text = result["en"].read_text()
            self.assertIn('id="_1"', text)
            self.assertIn("fresh", text)
            self.assertNotIn("edit", text)
            self.assertNotIn("script", text)
            self.assertNotIn("discard", text)

    def test_extraction_rewrites_zh_relative_links(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            site = p / "site"
            site.mkdir()
            (site / "index.zh-CN").mkdir()
            for f in [site / "index.html", site / "index.zh-CN/index.html"]:
                f.write_text(
                    '<article><h1 id="_1">x</h1><a href="../contracts.zh-CN/#x">next</a><a href="#_1">here</a></article>'
                )
            result = extract_reference_home(site, p / "out")
            self.assertIn(
                'href="/quant-backtest-engine/contracts.zh-CN/#x"',
                result["zh-CN"].read_text(),
            )
            self.assertIn(
                'href="/quant-backtest-engine/index.zh-CN/#_1"',
                result["zh-CN"].read_text(),
            )
