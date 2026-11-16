"""Verify an exact merged revision and every receipt-listed public site byte."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"unexpected redirect: {req.full_url}")


def fetch_bytes(url: str) -> bytes:
    """Bounded retries for transient reads; content mismatches are never retried."""
    for attempt in range(3):
        try:
            request = Request(url, headers={"Accept-Encoding": "identity", "Cache-Control": "no-cache"})
            with build_opener(RejectRedirects()).open(request, timeout=30) as response:
                if response.url != url:
                    raise ValueError(f"unexpected redirect: {url}")
                return response.read()
        except HTTPError as exc:
            if exc.code not in (500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def verify_deployed_site(base_url: str, expected_revision: str) -> dict:
    base = urlsplit(base_url)
    if (base.scheme != "https" or not base.netloc or base.query or base.fragment
            or base.username or base.password or not base.path.endswith("/")):
        raise ValueError("base must be an HTTPS directory URL without credentials/query/fragment")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise ValueError("expected revision must be a full Git commit")
    raw = fetch_bytes(base_url + "site-build.json")
    receipt = json.loads(raw)
    if receipt.get("schema") != "engine-site-build.v1":
        raise ValueError("unsupported build receipt")
    if receipt.get("identity", {}).get("source_revision") != expected_revision:
        raise ValueError("deployed revision differs from expected merged revision")
    files = receipt.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("empty or invalid delivered file map")
    for name, record in files.items():
        if (not isinstance(name, str) or name == "site-build.json"
                or any(c in name for c in "\\%?#:")
                or any(part in ("", ".", "..") for part in name.split("/"))):
            raise ValueError(f"unsafe receipt path: {name}")
        if not isinstance(record, dict):
            raise ValueError(f"invalid file record: {name}")
        digest = record.get("sha256")
        if type(record.get("bytes")) is not int or record["bytes"] < 0:
            raise ValueError(f"invalid file size: {name}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid file digest: {name}")

    def check(item):
        name, record = item
        expected = record["sha256"]
        data = fetch_bytes(base_url + quote(name, safe="/"))
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected or len(data) != record["bytes"]:
            raise ValueError(f"deployed hash mismatch: {name}")
        return name, actual

    with ThreadPoolExecutor(max_workers=8) as pool:
        verified = dict(pool.map(check, sorted(files.items())))
    # Detect publication during the check rather than combining two deployments.
    if fetch_bytes(base_url + "site-build.json") != raw:
        raise ValueError("deployed receipt changed during verification")
    return {
        "schema": "engine-deployed-verification.v1",
        "url": base_url,
        "source_revision": expected_revision,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "verified_files": len(verified),
        "files": verified,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be a new external receipt path")
    result = verify_deployed_site(args.url, args.revision)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}))


if __name__ == "__main__":
    main()
