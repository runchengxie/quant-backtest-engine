"""Validate rendered locales, counterparts, theme controls and local site links."""

from __future__ import annotations

import argparse
import re
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
    ]:
        for chinese in [False, True]:
            suffix = ".zh-CN" if chinese else ""
            relative = (
                "index.html"
                if name == "index" and not chinese
                else f"{name}{suffix}/index.html"
            )
            text = (root / relative).read_text(encoding="utf-8")
            language = "zh" if chinese else "en"
            assert f'<html lang="{language}"' in text, relative
            dark, light = (
                ("切换至深色模式", "切换至浅色模式")
                if chinese
                else ("Switch to dark mode", "Switch to light mode")
            )
            assert f'aria-label="{dark}"' in text and f'aria-label="{light}"' in text, (
                relative
            )
            assert (
                'data-md-color-scheme="default"' in text
                and 'data-md-color-scheme="slate"' in text
            ), relative
            nav = text.split("md-sidebar--primary", 1)[1].split(
                "md-sidebar--secondary", 1
            )[0]
            footer = re.search(r'<nav[^>]*class="md-footer__inner.*?</nav>', text, re.S)
            if footer:
                footer_links = Links()
                footer_links.feed(footer.group())
                for href in footer_links.links:
                    assert (".zh-CN" in href) == chinese, (
                        f"footer crosses locales: {relative}: {href}"
                    )
            expected, excluded = (
                ("输入输出契约", "Request and result contracts")
                if chinese
                else ("Request and result contracts", "输入输出契约")
            )
            assert expected in nav and excluded not in nav, relative
            counterpart = (
                (f"{name}/" if name != "index" else "") if chinese else f"{name}.zh-CN/"
            )
            assert (
                f"https://runchengxie.github.io/quant-backtest-engine/{counterpart}"
                in text
            ), relative
    print(
        "Rendered locales, theme controls, counterpart links and local assets verified"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-dir", type=Path, required=True)
    check(parser.parse_args().site_dir)
