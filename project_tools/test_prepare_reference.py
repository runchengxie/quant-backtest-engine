"""Direct Markdown semantics and legacy URL compatibility, without MkDocs."""

import unittest

from project_tools.prepare_reference import local_url, render_markdown


class ReferencePreparationTests(unittest.TestCase):
    def test_markdown_extensions_and_local_links(self):
        text = render_markdown(
            '# Title\n\n## 中文标题\n\n| A | B |\n| - | - |\n| 1 | 2 |\n\n!!! note "Read"\n    Body\n\n??? details "More"\n    Details\n\n[Next](../contracts.zh-CN.md#x)\n\n```python\nprint(1)\n```',
            "concepts/example.md",
        )
        for expected in [
            "<table>",
            'class="admonition note"',
            "<details",
            'id="_1"',
            "/quant-backtest-engine/contracts.zh-CN/#x",
            "<code",
        ]:
            self.assertIn(expected, text)

    def test_assets_fragments_and_external_urls(self):
        self.assertEqual(
            local_url("../assets/example.json", "guides/example.md"),
            "/quant-backtest-engine/assets/example.json",
        )
        self.assertEqual(local_url("#hello", "guides/example.md"), "#hello")
        self.assertEqual(
            local_url("https://example.com/a.md", "index.md"),
            "https://example.com/a.md",
        )

    def test_all_baseline_headings_remain_native_content_anchors(self):
        import json

        from project_tools.prepare_reference import ROOT, Metadata

        baseline = json.loads(
            (ROOT / "docs/site/legacy-route-anchors.json").read_text()
        )["html"]
        for name, expected in baseline.items():
            if name == "404.html":
                continue
            source = (
                "index.md"
                if name == "index.html"
                else name.removesuffix("/index.html") + ".md"
            )
            path = ROOT / "docs" / source
            self.assertTrue(path.is_file(), source)
            parsed = Metadata()
            parsed.feed(render_markdown(path.read_text(), source))
            self.assertEqual(
                set(expected["heading_ids"]) - set(parsed.ids), set(), name
            )
            self.assertEqual(len(parsed.ids), len(set(parsed.ids)), name)
