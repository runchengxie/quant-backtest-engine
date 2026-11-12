"""Produce a fresh, collision-free union with one owner per delivered path."""

from __future__ import annotations
import argparse
import gzip
import json
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

try:
    from .inventory_site_routes import inventory_site_routes, safe_files, sha256
    from .site_identity import input_identity
except ImportError:
    from inventory_site_routes import inventory_site_routes, safe_files, sha256
    from site_identity import input_identity
ROOTS = {"index.html", "index.zh-CN/index.html"}


def assemble_site(
    mkdocs_dir: Path,
    astro_dir: Path,
    learning_dir: Path,
    route_manifest: Path,
    output_dir: Path,
) -> Path:
    config = json.loads(route_manifest.read_text())
    if (
        config["schema"] != "engine-site-routes.v1"
        or set(config["replaced_html"]) != ROOTS
    ):
        raise ValueError("only the two roots may be replaced")
    if output_dir.exists():
        raise ValueError("assembled output must not already exist")
    inputs = {}
    owned = {}
    for owner, root in [("mkdocs", mkdocs_dir), ("astro", astro_dir)]:
        for source in safe_files(root):
            name = source.relative_to(root).as_posix()
            if owner == "mkdocs" and name in ROOTS:
                continue
            if name in inputs:
                raise ValueError(f"duplicate output: {name}")
            if name in {"sitemap.xml", "sitemap.xml.gz"} and owner == "mkdocs":
                continue
            if name == "renderer-input.json":
                continue
            valid = (
                (name in config[owner + "_html"])
                if name.endswith(".html")
                else (
                    name in config.get(owner + "_asset_files", [])
                    or any(
                        name.startswith(x) for x in config[owner + "_asset_prefixes"]
                    )
                )
            )
            if not valid:
                raise ValueError(f"undeclared {owner} output: {name}")
            inputs[name] = source
            owned[name] = owner
    if not ROOTS.issubset(inputs):
        raise ValueError("Astro must supply both roots")
    for source in safe_files(learning_dir):
        name = "assets/learning/" + source.relative_to(learning_dir).as_posix()
        if (
            name not in inputs
            or owned[name] != "mkdocs"
            or sha256(inputs[name]) != sha256(source)
        ):
            raise ValueError(f"learning bytes mismatch: {name}")
    identities = []
    for root in [mkdocs_dir, astro_dir]:
        receipt = root / "renderer-input.json"
        if receipt.exists():
            identities.append(json.loads(receipt.read_text()))
    if (identities or config.get("require_renderer_identity")) and (
        len(identities) != 2
        or identities[0] != identities[1]
        or identities[0] != input_identity()
    ):
        raise ValueError("renderer source identities differ")
    output_dir.mkdir(parents=True)
    for name, source in inputs.items():
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    routes = [
        name[:-10] if name.endswith("index.html") else name
        for name in inputs
        if name.endswith(".html") and name != "404.html"
    ]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(
            "<url><loc>"
            + escape(config["origin"] + config["base"] + route)
            + "</loc></url>"
            for route in sorted(routes)
        )
        + "</urlset>"
    )
    (output_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (output_dir / "sitemap.xml.gz").write_bytes(
        gzip.compress(sitemap.encode(), mtime=0)
    )
    inventory = inventory_site_routes(output_dir)
    receipt = {
        "schema": "engine-site-build.v1",
        "identity": input_identity(),
        "route_manifest_sha256": sha256(route_manifest),
        "files": inventory["files"],
        "html": inventory["html"],
        "owners": owned,
    }
    (output_dir / "site-build.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    return output_dir


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for arg in ["mkdocs", "astro", "learning", "routes", "output"]:
        p.add_argument("--" + arg, type=Path, required=True)
    a = p.parse_args()
    assemble_site(a.mkdocs, a.astro, a.learning, a.routes, a.output)
