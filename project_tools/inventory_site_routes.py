"""Inventory actual emitted bytes and HTML, never inferred Markdown slugs."""

from __future__ import annotations
import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.heading_ids = []
        self.control_ids = []
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
            if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                self.heading_ids.append(attrs["id"])
            if tag in {"button", "select", "input", "textarea", "output"}:
                self.control_ids.append(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key):
                self.hrefs.append(attrs[key])

    def record(self):
        return {
            key: getattr(self, key)
            for key in ("ids", "heading_ids", "control_ids", "hrefs")
        }


def safe_files(root: Path):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid input root")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink forbidden: {path.name}")
        if path.is_file():
            yield path


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_site_routes(site_dir: Path) -> dict:
    files = {}
    html = {}
    for path in safe_files(site_dir):
        name = path.relative_to(site_dir).as_posix()
        files[name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
        if path.suffix == ".html":
            parser = Page()
            parser.feed(path.read_text(encoding="utf-8"))
            html[name] = parser.record()
    return {"schema": "engine-site-inventory.v1", "files": files, "html": html}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--site-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source-revision", required=True)
    a = p.parse_args()
    result = inventory_site_routes(a.site_dir)
    result["source_revision"] = a.source_revision
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
