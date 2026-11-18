"""Deployed delivery checks fail closed on stale, altered or unsafe content."""

import hashlib
import json
import unittest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from scripts.verify.verify_deployed_site import fetch_bytes, verify_deployed_site


class DeployedSiteTests(unittest.TestCase):
    def setUp(self):
        self.revision = "a" * 40
        self.files = {"index.html": b"English", "index.zh-CN/index.html": b"Chinese",
                      "assets/learning/manifest.json": b"{}"}
        self.receipt = {"schema": "engine-site-build.v1",
                        "identity": {"source_revision": self.revision},
                        "files": {k: {"sha256": hashlib.sha256(v).hexdigest(), "bytes": len(v)}
                                  for k, v in self.files.items()}}

    def run_check(self):
        payloads = {**self.files, "site-build.json": json.dumps(self.receipt).encode()}
        def fetch(url):
            self.assertTrue(url.startswith("https://example.test/engine/"))
            return payloads[url.removeprefix("https://example.test/engine/")]
        with patch("scripts.verify.verify_deployed_site.fetch_bytes", side_effect=fetch):
            return verify_deployed_site("https://example.test/engine/", self.revision)

    def test_checks_all_files_and_source(self):
        result = self.run_check()
        self.assertEqual(result["verified_files"], 3)
        self.assertEqual(result["source_revision"], self.revision)

    def test_empty_pages_marker_is_artifact_only(self):
        self.receipt["files"][".nojekyll"] = {"sha256": hashlib.sha256(b"").hexdigest(), "bytes": 0}
        # No HTTP payload exists for this artifact control file.
        result = self.run_check()
        self.assertEqual(result["verified_files"], 3)
        self.assertEqual(list(result["artifact_only_files"]), [".nojekyll"])

    def test_marker_alone_is_not_a_public_site(self):
        self.receipt["files"] = {".nojekyll": {"sha256": hashlib.sha256(b"").hexdigest(), "bytes": 0}}
        with self.assertRaisesRegex(ValueError, "no public files"):
            self.run_check()

    def test_nonempty_pages_marker_is_rejected(self):
        for size in (0, 7):
            self.receipt["files"][".nojekyll"] = {"sha256": hashlib.sha256(b"payload").hexdigest(), "bytes": size}
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "marker"):
                self.run_check()

    def test_other_missing_files_are_not_skipped(self):
        self.receipt["files"]["assets/missing.js"] = {"sha256": hashlib.sha256(b"").hexdigest(), "bytes": 0}
        with self.assertRaises(KeyError):
            self.run_check()

    def test_stale_source_fails(self):
        self.receipt["identity"]["source_revision"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "revision"):
            self.run_check()

    def test_changed_delivered_bytes_fail(self):
        self.files["index.html"] = b"stale English"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_check()

    def test_unsafe_paths_fail_before_file_fetch(self):
        for path in ("../outside", "/outside", "https://other.test/x", "x?y", "x#y",
                     "x\\y", "%2e%2e/x", "x//y", "./x", "site-build.json"):
            with self.subTest(path=path):
                self.receipt["files"] = {path: "a" * 64}
                with self.assertRaisesRegex(ValueError, "path"):
                    self.run_check()

    def test_empty_or_invalid_file_map_fails(self):
        for files in ({}, {"index.html": "wrong"}):
            self.receipt["files"] = files
            with self.assertRaises(ValueError):
                self.run_check()

    def test_only_https_base_without_query_is_accepted(self):
        for url in ("http://example.test/", "https://example.test/?x", "https://u:p@example.test/"):
            with self.assertRaises(ValueError):
                verify_deployed_site(url, self.revision)

    def test_receipt_change_during_download_fails(self):
        raw = json.dumps(self.receipt).encode()
        calls = 0
        def fetch(url):
            nonlocal calls
            name = url.removeprefix("https://example.test/engine/")
            if name == "site-build.json":
                calls += 1
                return raw if calls == 1 else raw + b" "
            return self.files[name]
        with patch("scripts.verify.verify_deployed_site.fetch_bytes", side_effect=fetch):
            with self.assertRaisesRegex(ValueError, "changed during"):
                verify_deployed_site("https://example.test/engine/", self.revision)

    def test_wrong_size_fails_even_with_correct_hash(self):
        self.receipt["files"]["index.html"]["bytes"] += 1
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_check()

    def test_fetch_rejects_redirect_before_contacting_destination(self):
        visited = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                visited.append(self.path)
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/outside")
                else:
                    self.send_response(200)
                self.end_headers()
            def log_message(self, *args):
                pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with self.assertRaisesRegex(ValueError, "redirect"):
                fetch_bytes(f"http://127.0.0.1:{server.server_port}/redirect")
            self.assertEqual(visited, ["/redirect"])
        finally:
            server.shutdown()
            worker.join(timeout=2)
            server.server_close()
