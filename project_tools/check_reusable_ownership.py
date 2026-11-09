"""Check declared ownership and route continuity; never execute acceptance commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
from urllib.parse import urlsplit

LOCALES = ("en", "zh-CN")
WAVES = tuple(f"M{i}" for i in range(8)) + ("later-rust-parity",)
GATES = ("M0", "A", "B", "C", "R", "T", "delivery", "retain")
REMOVAL_GATES = ("two-minors-and-all-consumers", "retain")
REQUIRED = ("symbol", "old_module", "new_module", "provider_version", "compatibility_path")


def _revision_exists(root: Path, revision: str, source: str = "") -> bool:
    target = f"{revision}:{source}" if source else f"{revision}^{{commit}}"
    result = subprocess.run(["git", "-C", str(root), "cat-file", "-e", target],
                            capture_output=True, check=False)
    return result.returncode == 0


def check_ownership(path: Path) -> list[str]:
    """Return precise errors, allowing future rows without inventing source evidence.

    Implemented sources must be in this repository at the stated revision AND in
    the current tree. Release/deployment receipts are a separate publication step.
    Historical locale declarations are explicit; suffixes never override them.
    """
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"cannot read ownership registry: {exc}"]
    if not isinstance(data, dict) or data.get("schema") != "engine-ownership.v1":
        return ["schema must be engine-ownership.v1"]
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return ["rows must be a nonempty list"]
    historical = {}
    historical_routes = data.get("historical_routes", [])
    if not isinstance(historical_routes, list):
        errors.append("historical_routes must be a list")
        historical_routes = []
    for route in historical_routes:
        if not isinstance(route, dict) or route.get("locale") not in LOCALES or not isinstance(route.get("url"), str):
            errors.append("invalid historical route declaration")
            continue
        url, locale = route["url"], route["locale"]
        if url in historical and historical[url] != locale:
            errors.append(f"conflicting historical route language: {url}")
        historical[url] = locale
    symbols, mappings = set(), {}
    root = path.resolve().parents[2]
    for index, row in enumerate(rows):
        prefix = f"row {index}"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in REQUIRED:
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"{prefix}: {field} must be nonempty")
        symbol = row.get("symbol")
        if isinstance(symbol, str):
            if symbol in symbols:
                errors.append(f"{prefix}: duplicate symbol {symbol}")
            symbols.add(symbol)
        status = row.get("status")
        if status not in ("planned", "implemented"):
            errors.append(f"{prefix}: status must be planned or implemented")
        if row.get("wave") not in WAVES:
            errors.append(f"{prefix}: unknown wave")
        if row.get("gate") not in GATES:
            errors.append(f"{prefix}: unknown gate")
        if row.get("removal_gate") not in REMOVAL_GATES:
            errors.append(f"{prefix}: unknown removal_gate")
        command = row.get("acceptance_test")
        try:
            args = shlex.split(command) if isinstance(command, str) else []
        except ValueError:
            args = []
        if len(args) < 2 or args[0] not in {"python", "python3", "cargo", "uv", "node"}:
            errors.append(f"{prefix}: acceptance_test must name an executable command")
        if "source_revision" not in row:
            errors.append(f"{prefix}: source_revision field is required")
        revision = row.get("source_revision")
        valid_revision = isinstance(revision, str) and bool(re.fullmatch(r"[0-9a-f]{40}", revision)) and revision != "0" * 40
        if (revision is not None or status == "implemented") and not valid_revision:
            errors.append(f"{prefix}: source_revision must be a real full commit (null only for planned rows)")
        if valid_revision and not _revision_exists(root, revision):
            errors.append(f"{prefix}: source_revision is not present in repository history")
        sources = row.get("provider_sources")
        if not isinstance(sources, list) or not sources or not all(isinstance(s, str) and s for s in sources):
            errors.append(f"{prefix}: provider_sources must name provider files")
            sources = []
        if status == "implemented":
            for source in sources:
                candidate = (root / source).resolve()
                if (not candidate.is_relative_to(root) or not candidate.is_file()
                        or not valid_revision or not _revision_exists(root, revision, source)):
                    errors.append(f"{prefix}: provider source missing at source_revision/current tree: {source}")
        routes = {}
        for field in ("old_urls", "new_urls"):
            values = row.get(field)
            by_locale = {}
            if field == "old_urls" and not values:
                errors.append(f"{prefix}: old_urls must name a historical route")
            if not isinstance(values, list):
                errors.append(f"{prefix}: {field} must be a route list")
                values = []
            for route in values:
                if not isinstance(route, dict):
                    errors.append(f"{prefix}: invalid {field} route")
                    continue
                locale, url, anchors = route.get("locale"), route.get("url"), route.get("anchors")
                if locale not in LOCALES or not isinstance(url, str):
                    errors.append(f"{prefix}: invalid {field} locale/url")
                    continue
                parsed = urlsplit(url)
                if parsed.scheme != "https" or not parsed.netloc or parsed.fragment:
                    errors.append(f"{prefix}: {field} needs an absolute HTTPS page URL without fragment")
                if not isinstance(anchors, list) or not all(isinstance(a, str) and a and not a.startswith("#") for a in anchors):
                    errors.append(f"{prefix}: invalid {field} anchors")
                    anchors = []
                if field == "old_urls" and url in historical and historical[url] != locale:
                    errors.append(f"{prefix}: historical route language changed: {url}")
                if locale in by_locale:
                    errors.append(f"{prefix}: duplicate {field} locale {locale}")
                by_locale[locale] = (url, tuple(anchors))
                if field == "new_urls" and status == "implemented":
                    base = "/quant-backtest-engine/"
                    relative = parsed.path.removeprefix(base).rstrip("/")
                    source = root / "docs" / (f"{relative}.md" if relative else "index.md")
                    if parsed.netloc != "runchengxie.github.io" or not parsed.path.startswith(base) or not source.is_file():
                        errors.append(f"{prefix}: destination documentation missing: {url}")
            if field == "new_urls":
                for locale in sorted(set(LOCALES) - by_locale.keys()):
                    errors.append(f"{prefix}: {field} missing locale {locale}")
            routes[field] = by_locale
        destinations = routes["new_urls"]
        if len(destinations) == 2 and destinations["en"][0] == destinations["zh-CN"][0]:
            errors.append(f"{prefix}: destination locales share one page")
        for locale, old in routes["old_urls"].items():
            destination = routes["new_urls"].get(locale)
            key = (locale, old[0])
            if destination and key in mappings and mappings[key] != destination:
                errors.append(f"{prefix}: conflicting route mapping: {old[0]}")
            elif destination:
                mappings[key] = destination
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "docs/migration/reusable-ownership.json")
    errors = check_ownership(parser.parse_args().path)
    for error in errors:
        print(error)
    if not errors:
        print("Ownership registry, historical locale declarations and migration gates verified")
    raise SystemExit(bool(errors))
