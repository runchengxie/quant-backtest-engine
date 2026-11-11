"""Validate delivered hashes, every local URL/fragment, and actual baseline IDs."""

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

try:
    from .inventory_site_routes import inventory_site_routes
except ImportError:
    from inventory_site_routes import inventory_site_routes


def check_assembled_site(site_dir: Path, base: str, legacy: Path):
    inventory = inventory_site_routes(site_dir)
    receipt = json.loads((site_dir / "site-build.json").read_text())
    actual = {k: v for k, v in inventory["files"].items() if k != "site-build.json"}
    if receipt["files"] != actual:
        raise ValueError("delivered bytes differ from receipt")
    old = json.loads(legacy.read_text())
    for name, page in old["html"].items():
        if name not in inventory["html"]:
            raise ValueError(f"missing legacy route {name}")
        missing = set(page["ids"]) - set(inventory["html"][name]["ids"])
        if missing:
            raise ValueError(f"missing legacy IDs {name}: {missing}")

    def check_url(name, href):
        u = urlsplit(href)
        if u.scheme or u.netloc:
            return
        resolved = urlsplit(urljoin(base + name, href))
        path = unquote(resolved.path)
        if not path.startswith(base):
            raise ValueError(f"link outside base {name}: {href}")
        relative = path[len(base) :]
        if not relative or relative.endswith("/"):
            relative += "index.html"
        if relative not in inventory["files"]:
            raise ValueError(f"missing target {name}: {href}")
        if (
            resolved.fragment
            and relative in inventory["html"]
            and unquote(resolved.fragment) not in inventory["html"][relative]["ids"]
        ):
            raise ValueError(f"missing fragment {name}: {href}")

    for name, page in inventory["html"].items():
        for href in page["hrefs"]:
            check_url(name, href)
    search = site_dir / "search/search_index.json"
    if search.exists():
        for doc in json.loads(search.read_text())["docs"]:
            check_url("index.html", doc["location"])
    return {"html": len(inventory["html"]), "files": len(actual)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--site-dir", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--legacy", type=Path, required=True)
    a = p.parse_args()
    print(check_assembled_site(a.site_dir, a.base, a.legacy))
