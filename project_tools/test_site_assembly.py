import json
import tempfile
import unittest
from pathlib import Path

from project_tools.assemble_site import assemble_site


class AssemblyTests(unittest.TestCase):
    def prepare(self, d):
        p = Path(d)
        dirs = [p / x for x in ["mk", "astro", "learning"]]
        for x in dirs:
            x.mkdir()
        mk, astro, learning = dirs
        for x in [mk, astro]:
            (x / "index.html").write_text('<h1 id="root">home</h1>')
            (x / "index.zh-CN").mkdir()
            (x / "index.zh-CN/index.html").write_text('<h1 id="_1">首页</h1>')
        (mk / "search").mkdir()
        (mk / "search/search_index.json").write_text('{"docs":[{"location":"#root"}]}')
        manifest = p / "routes.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": "engine-site-routes.v1",
                    "base": "/quant-backtest-engine/",
                    "origin": "https://runchengxie.github.io",
                    "replaced_html": ["index.html", "index.zh-CN/index.html"],
                    "astro_html": ["index.html", "index.zh-CN/index.html"],
                    "mkdocs_html": ["index.html", "index.zh-CN/index.html"],
                    "mkdocs_asset_prefixes": [
                        "search/",
                        "assets/",
                        "javascripts/",
                        "stylesheets/",
                    ],
                    "mkdocs_asset_files": [],
                    "astro_asset_prefixes": ["_astro/"],
                }
            )
        )
        return mk, astro, learning, manifest, p / "out"

    def test_roots_are_only_html_replacements(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.prepare(d)
            (args[0] / "extra.html").write_text("old")
            (args[1] / "extra.html").write_text("new")
            with self.assertRaises(ValueError):
                assemble_site(*args)

    def test_duplicate_asset_path_fails_even_when_bytes_equal(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.prepare(d)
            for p in args[:2]:
                (p / "same.txt").write_text("equal")
            with self.assertRaises(ValueError):
                assemble_site(*args)

    def test_base_path_search_and_sitemap_links(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.prepare(d)
            result = assemble_site(*args)
            self.assertIn(
                "https://runchengxie.github.io/quant-backtest-engine/index.zh-CN/",
                (result / "sitemap.xml").read_text(),
            )
            receipt = json.loads((result / "site-build.json").read_text())
            self.assertNotIn("site-build.json", receipt["files"])
            self.assertIn("search/search_index.json", receipt["files"])


class AstroAssemblyTests(unittest.TestCase):
    def test_one_owner_rejects_unlisted_html_and_stale_identity(self):
        from project_tools.assemble_site import assemble_astro
        from project_tools.site_identity import input_identity

        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            astro = p / "astro"
            astro.mkdir()
            learning = p / "learning"
            learning.mkdir()
            config = {
                "astro_html": ["index.html"],
                "astro_asset_files": [],
                "astro_asset_prefixes": [],
                "base": "/quant-backtest-engine/",
                "origin": "https://example.com",
            }
            routes = p / "routes.json"
            routes.write_text(json.dumps(config))
            (astro / "index.html").write_text('<h1 id="home">Home</h1>')
            (astro / "renderer-input.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "identities"):
                assemble_astro(astro, learning, routes, p / "out")
            (astro / "renderer-input.json").write_text(json.dumps(input_identity()))
            (astro / "unexpected.html").write_text("extra")
            with self.assertRaisesRegex(ValueError, "undeclared"):
                assemble_astro(astro, learning, routes, p / "out")
            (astro / "unexpected.html").unlink()
            result = assemble_astro(astro, learning, routes, p / "out")
            self.assertEqual(
                json.loads((result / "site-build.json").read_text())["owners"],
                {"index.html": "astro"},
            )
