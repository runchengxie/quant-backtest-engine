"""Same-source build inputs, separate from delivered artifact byte identity."""

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def input_identity():
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    names = sorted(
        set(
            n
            for n in names
            if n.startswith(("docs/", "web/", "project_tools/", ".github/workflows/")) or n == "mkdocs.yml"
        )
    )
    hashes = {
        n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
        for n in names
        if (ROOT / n).is_file() and not (ROOT / n).is_symlink()
    }
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    return {
        "source_revision": revision,
        "source_sha256": hashlib.sha256(
            "\n".join(f"{n}:{h}" for n, h in hashes.items()).encode()
        ).hexdigest(),
        "inputs": hashes,
    }
