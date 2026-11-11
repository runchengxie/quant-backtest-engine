"""Extract fresh trusted MkDocs article fragments, preserving original link bases."""

from __future__ import annotations
import argparse
import html
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

try:
    from .inventory_site_routes import Page, sha256
    from .site_identity import input_identity
except ImportError:
    from inventory_site_routes import Page, sha256
    from site_identity import input_identity
BASE = "/quant-backtest-engine/"
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class Article(HTMLParser):
    def __init__(self, route):
        super().__init__(convert_charrefs=False)
        self.route = route
        self.depth = 0
        self.skip = 0
        self.parts = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if not self.depth:
            if tag != "article":
                return
            self.depth = 1
            self.count += 1
            return
        if tag not in VOID:
            self.depth += 1
        if self.skip:
            if tag not in VOID:
                self.skip += 1
            return
        if tag == "script" or "md-content__button" in values.get("class", "").split():
            if tag not in VOID:
                self.skip = 1
            return
        result = []
        for key, value in attrs:
            if key.startswith("on"):
                continue
            if value is not None and key in {"href", "src"}:
                url = urlsplit(value)
                if not url.scheme and not url.netloc:
                    value = urljoin(BASE + self.route, value)
            result.append(
                key if value is None else f'{key}="{html.escape(value, quote=True)}"'
            )
        self.parts.append("<" + tag + (" " + " ".join(result) if result else "") + ">")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.depth:
            return
        self.depth -= 1
        if self.skip:
            self.skip -= 1
            return
        if self.depth:
            self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)

    def handle_entityref(self, name):
        self.handle_data("&" + name + ";")

    def handle_charref(self, name):
        self.handle_data("&#" + name + ";")


def extract_reference_home(site_dir: Path, output_dir: Path) -> dict[str, Path]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("fragment output must be fresh")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    records = {}
    for locale, route, file in [
        ("en", "", "index.html"),
        ("zh-CN", "index.zh-CN/", "index.zh-CN/index.html"),
    ]:
        source = site_dir / file
        if source.is_symlink():
            raise ValueError("symlink root")
        parser = Article(route)
        parser.feed(source.read_text(encoding="utf-8"))
        if parser.count != 1 or parser.depth:
            raise ValueError("expected one complete article")
        content = "".join(parser.parts)
        ids = Page()
        ids.feed(content)
        if len(ids.ids) != len(set(ids.ids)):
            raise ValueError("duplicate article ID")
        target = output_dir / (locale + ".html")
        target.write_text(content, encoding="utf-8")
        result[locale] = target
        records[locale] = {
            "source": file,
            "source_sha256": sha256(source),
            "fragment": target.name,
            "sha256": sha256(target),
            "ids": ids.ids,
        }
    (output_dir / "receipt.json").write_text(
        json.dumps(
            {
                "schema": "engine-reference-home.v1",
                "identity": input_identity(),
                "fragments": records,
            },
            indent=2,
        )
        + "\n"
    )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--site-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    extract_reference_home(a.site_dir, a.output)
