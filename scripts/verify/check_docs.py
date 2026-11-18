"""Validate rendered locales, counterparts, theme controls and local site links."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag in {"a", "link"} and values.get("href"):
            self.links.append(values["href"])
        if tag in {"script", "img"} and values.get("src"):
            self.links.append(values["src"])


import sys
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

def check(site: Path) -> None:
    root = site.resolve()
    for path in root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        parsed = Links()
        parsed.feed(text)
        for href in parsed.links:
            url = urlsplit(href)
            if url.scheme or url.netloc:
                continue
            if not url.path:
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if url.path.startswith("/quant-backtest-engine/"):
                target = root / unquote(
                    url.path.removeprefix("/quant-backtest-engine/")
                )
            if target.is_dir():
                target /= "index.html"
            assert target.is_relative_to(root) and target.is_file(), (
                f"broken local link: {path}: {href}"
            )
    for name in [
        "index",
        "quickstart",
        "tutorial",
        "backtesting-explained",
        "capabilities",
        "correctness",
        "benchmarks",
        "releases",
        "contracts",
        "execution",
        "runtime",
        "development",
        "third-party-notices",
        "sizing",
        "sessions",
        "migration/corporate-action-conformance",
        "migration/reusable-product",
        "python-client",
        "product/contracts",
        "product/installation",
        "product/backends",
        "product/recovery",
        "concepts/impact-planning",
        "product/joint-execution",
        "backtest/capital-and-reconciliation",
        "backtest/market-paths",
        "backtest/transaction-cost-evidence",
        "backtest/execution-integrity",
        "backtest/cost-evidence",
        "backtest/minute-session",
        "guides/minute-execution",
    ]:
        for chinese in [False, True]:
            suffix = ".zh-CN" if chinese else ""
            relative = (
                "index.html"
                if name == "index" and not chinese
                else f"{name}{suffix}/index.html"
            )
            text = (root / relative).read_text(encoding="utf-8")
            language = "zh-CN" if chinese else "en"
            assert f'<html lang="{language}"' in text, relative
            assert 'id="product-theme"' in text, relative
            if name != "index":
                assert 'id="reference-query"' in text, relative
            counterpart = (
                (f"{name}/" if name != "index" else "") if chinese else f"{name}.zh-CN/"
            )
            assert f'href="/quant-backtest-engine/{counterpart}"' in text, relative
            # Actual legacy IDs and every local link/fragment are checked separately
            # by check_assembled_site, against the immutable observed baseline.
    import json

    from scripts.build.method_docs import ASSETS

    fixtures = json.loads((ASSETS / "fixtures.json").read_text())
    for suffix in ["", ".zh-CN"]:
        text = (root / f"backtesting-explained{suffix}/index.html").read_text(
            encoding="utf-8"
        )
        assert text.count('class="method-scene"') == 8
        assert text.count('class="method-payload"') == 8
        for scene in fixtures["scenes"].values():
            for scenario in scene["scenarios"]:
                for index in range(len(scenario["states"])):
                    assert (
                        f'data-scenario="{scenario["id"]}" data-frame="{index}"' in text
                    )
        assert "10019.78" in text and "10989" in text
        assert 'aria-live="polite"' in text and 'scope="col"' in text
        assert (
            "javascripts/method-replay.js" in text
            and "stylesheets/method-replay.css" in text
        )
    print(
        "Rendered locales, theme controls, counterpart links and local assets verified"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-dir", type=Path, required=True)
    check(parser.parse_args().site_dir)
