"""Build experimental Linux archives from a committed tree, with offline sources.

All generated files live under --output (which must be outside the repository).
No publication is performed by this command. Requires Python 3.11+, Rust 1.99.0,
Cargo, git, and Linux x86_64 native build prerequisites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = "1.99.0"
TARGET = "x86_64-unknown-linux-gnu"


# Published crates below omit repository-wide license files. Preserve authentic,
# reviewed texts outside vendor/ without modifying Cargo-checksummed sources.
SUPPLEMENTS = {
    "nautilus-macros-0.66.0": (
        "55c0e82053142bce3a5cba4de4221d3929c2d3bc",
        [
            (
                "LICENSE",
                "https://raw.githubusercontent.com/nautechsystems/nautilus_trader/55c0e82053142bce3a5cba4de4221d3929c2d3bc/LICENSE",
                "ee907919ec88c9c017b1f8b608db20960b6598aefcc4fe58820bde955d65ed3c",
            )
        ],
    ),
    "ruint-1.21.1": (
        "be3f8050d63d92a4c9f206d5a083ec538f9c6d58",
        [
            (
                "LICENSE",
                "https://raw.githubusercontent.com/alloy-rs/ruint/be3f8050d63d92a4c9f206d5a083ec538f9c6d58/LICENSE",
                "9de1e5b5b50b059e58009b7044705557dd07ec87555bca518bef8b5acc002908",
            )
        ],
    ),
    "ruint-macro-1.2.1": (
        "89d58efbd4c6de4994e5e404ed6450b8bb927202",
        [
            (
                "LICENSE",
                "https://raw.githubusercontent.com/recmo/uint/89d58efbd4c6de4994e5e404ed6450b8bb927202/LICENSE",
                "9de1e5b5b50b059e58009b7044705557dd07ec87555bca518bef8b5acc002908",
            )
        ],
    ),
}
for _crate in ("objc2-core-foundation-0.3.2", "objc2-io-kit-0.3.2"):
    SUPPLEMENTS[_crate] = (
        "7b1abfd750a2cacaea71d6a56ecfb83cb7de560b",
        [
            (
                "LICENSE.md",
                "https://raw.githubusercontent.com/madsmtm/objc2/7b1abfd750a2cacaea71d6a56ecfb83cb7de560b/LICENSE.md",
                "7f976f7e9cb2d87df7230606feb932c3f21ac0e664045a775b600046ff850c54",
            ),
            (
                "LICENSE-APACHE-2.0.txt",
                "https://www.apache.org/licenses/LICENSE-2.0.txt",
                "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
            ),
        ],
    )


def supplement_notices(crate: Path, destination: Path) -> list[dict]:
    package = tomllib.loads((crate / "Cargo.toml").read_text())["package"]
    identity = f"{package['name']}-{package['version']}"
    revision, files = SUPPLEMENTS[identity]
    vcs = json.loads((crate / ".cargo_vcs_info.json").read_text())
    if vcs["git"]["sha1"] != revision:
        raise RuntimeError(f"Unexpected source revision for {crate.name}")
    records = []
    for name, url, expected_hash in files:
        for attempt in range(3):
            try:
                with urlopen(url, timeout=60) as response:
                    content = response.read()
                break
            except (HTTPError, URLError) as error:
                if isinstance(error, HTTPError) and error.code not in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    raise
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected_hash:
            raise RuntimeError(f"Upstream license hash mismatch: {url}")
        target = destination / crate.name / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        records.append(
            {
                "path": f"{crate.name}/{name}",
                "url": url,
                "upstream_revision": revision,
                "sha256": digest,
            }
        )
    return records


def run(*args: str, cwd: Path = ROOT, env=None) -> str:
    return subprocess.check_output(args, cwd=cwd, env=env, text=True)


def license_inventory(vendor: Path, destination: Path) -> list[dict]:
    """Preserve published license/notice files and fail closed on absent texts."""
    inventory = []
    for crate in sorted(vendor.iterdir()):
        manifest = tomllib.loads((crate / "Cargo.toml").read_text())
        package = manifest["package"]
        notices = [
            p
            for p in crate.rglob("*")
            if p.is_file()
            and any(
                word in p.name.lower()
                for word in (
                    "license",
                    "licence",
                    "copying",
                    "copyright",
                    "notice",
                    "authors",
                )
            )
        ]
        license_file = package.get("license-file")
        if license_file and (crate / license_file).is_file():
            notices.append(crate / license_file)
        supplements = (
            supplement_notices(crate, destination / "supplemental")
            if f"{package['name']}-{package['version']}" in SUPPLEMENTS
            else []
        )
        if not notices and not supplements:
            raise RuntimeError(
                f"No license/notice text in vendored crate: {crate.name}"
            )
        for notice in sorted(set(notices)):
            relative = notice.relative_to(vendor)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(notice, target)
        inventory.append(
            {
                "name": package["name"],
                "version": package["version"],
                "license": package.get("license"),
                "license_file": license_file,
                "supplemental_notices": supplements,
                "notices": [str(p.relative_to(vendor)) for p in sorted(set(notices))],
            }
        )
    return inventory


def archive(directory: Path, output: Path) -> None:
    with tarfile.open(output, "w:gz") as tar:
        tar.add(directory, arcname=directory.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("--output must be outside the source repository")
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        parser.error("this experimental package supports Linux x86_64 only")
    output.mkdir(parents=True, exist_ok=True)
    revision = run("git", "rev-parse", "HEAD").strip()
    # Never silently distribute a binary built from edits absent from its sources.
    if run("git", "status", "--porcelain", "--untracked-files=normal").strip():
        parser.error("commit all source changes first; packaging requires a clean tree")
    with tempfile.TemporaryDirectory(prefix="release-build-", dir=output) as staging:
        staging = Path(staging)
        source = staging / "source"
        source.mkdir()
        source_tar = staging / "git-source.tar"
        subprocess.run(
            ["git", "archive", "--format=tar", "-o", str(source_tar), revision],
            cwd=ROOT,
            check=True,
        )
        with tarfile.open(source_tar) as tar:
            tar.extractall(source, filter="data")
        manifest = tomllib.loads((source / "Cargo.toml").read_text())
        version = manifest["package"]["version"]
        base = f"quant-backtest-engine-{version}-{TARGET}"
        for name in (f"{base}.tar.gz", f"{base}-source.tar.gz", "SHA256SUMS"):
            if (output / name).exists():
                parser.error(
                    f"refusing to overwrite existing release asset: {output / name}"
                )
        binary = staging / base
        binary.mkdir()
        # cargo vendor emits the exact registry-replacement config to stdout.
        config = run(
            "cargo", f"+{TOOLCHAIN}", "vendor", "--locked", "vendor", cwd=source
        )
        (source / ".cargo").mkdir(exist_ok=True)
        (source / ".cargo/config.toml").write_text(config)
        inventory = license_inventory(source / "vendor", binary / "dependency-notices")
        if (binary / "dependency-notices/supplemental").exists():
            shutil.copytree(
                binary / "dependency-notices/supplemental",
                source / "supplemental-dependency-notices",
            )
        (binary / "dependency-licenses.json").write_text(
            json.dumps(inventory, indent=2) + "\n"
        )
        shutil.copy2(binary / "dependency-licenses.json", source)
        env = dict(os.environ, CARGO_TARGET_DIR=str(staging / "target"))
        cargo = ["cargo", f"+{TOOLCHAIN}"]
        # An empty CARGO_HOME proves registry downloads/indexes are unnecessary.
        # RUSTUP_HOME is inherited independently; rustup still finds the toolchain.
        env["CARGO_HOME"] = str(staging / "offline-cargo-home")
        for command in (
            ["test", "--offline", "--locked", "--release", "--target", TARGET],
            ["build", "--offline", "--locked", "--release", "--target", TARGET],
        ):
            subprocess.run(cargo + command, cwd=source, env=env, check=True)
        shutil.copy2(
            staging / "target" / TARGET / "release/quant-backtest-engine", binary
        )
        for name in ("LICENSE", "COPYING"):
            shutil.copy2(source / name, binary)
        shutil.copy2(
            source / "docs/third-party-notices.md", binary / "THIRD-PARTY-NOTICES.md"
        )
        metadata = {
            "version": version,
            "source_revision": revision,
            "target": TARGET,
            "rustc": run("rustc", f"+{TOOLCHAIN}", "--version", "--verbose"),
            "cargo": run(*cargo, "--version").strip(),
            "build_platform": platform.platform(),
            "libc": run("getconf", "GNU_LIBC_VERSION").strip(),
            "profile": "release",
            "cargo_lock_sha256": hashlib.sha256(
                (source / "Cargo.lock").read_bytes()
            ).hexdigest(),
        }
        for tree in (source, binary):
            (tree / "BUILD-METADATA.json").write_text(
                json.dumps(metadata, indent=2) + "\n"
            )
        (source / "REBUILD.md").write_text("""# Offline rebuild and relink

Install Rust 1.99.0 with the x86_64-unknown-linux-gnu target and native build tools
(C compiler/linker, libc development headers; Ubuntu 22.04 build-essential).
From this directory, run:

    cargo +1.99.0 build --offline --locked --release --target x86_64-unknown-linux-gnu
    cargo +1.99.0 test --offline --locked
    target/x86_64-unknown-linux-gnu/release/quant-backtest-engine run fixtures/roundtrip.json

Cargo.lock, vendor/ (including published license texts), and .cargo/config.toml
are included. No registry access is required after toolchain/native setup.
The binary statically links Rust crates, including LGPL NautilusTrader crates;
these complete application/dependency sources allow rebuilding and relinking.
To modify a dependency, edit its vendor/<crate>/ sources and remove the modified
file's entry from that crate's .cargo-checksum.json `files` map (or use a local
path patch outside vendor). Cargo otherwise rejects edits to checksummed files.
Rebuild with the commands above; the resulting executable contains your changes.
Retain applicable copyright and license notices when redistributing.

These instructions support repeatable source builds, not a guarantee of identical
binary bytes across machines or a legal compliance opinion. Native build tools
and the Rust toolchain are external prerequisites, not included in this archive.
""")
        (binary / "README.txt").write_text(
            "Experimental Linux x86_64 / glibc CLI. Built on Ubuntu 22.04 in release CI; "
            "see BUILD-METADATA.json for the actual local build baseline.\n"
            "Run ./quant-backtest-engine capabilities or ./quant-backtest-engine run REQUEST.json.\n"
            "Download the matching source archive alongside this binary. It includes all locked "
            "Rust dependency sources, license texts and offline rebuild/relink instructions.\n"
            "LGPL-3.0-only; preserve LICENSE, COPYING and dependency notices.\n"
        )
        source.rename(staging / f"{base}-source")
        source = staging / f"{base}-source"
        archive(binary, output / f"{base}.tar.gz")
        archive(source, output / f"{base}-source.tar.gz")
        # Smoke the actual unpacked distribution, not only a build-tree executable.
        smoke = staging / "smoke"
        smoke.mkdir()
        with tarfile.open(output / f"{base}.tar.gz") as tar:
            tar.extractall(smoke, filter="data")
        executable = smoke / base / "quant-backtest-engine"
        subprocess.run([str(executable), "capabilities"], check=True)
        result = json.loads(
            run(str(executable), "run", str(source / "fixtures/roundtrip.json"))
        )
        if result.get("equity") != "10019.78" or result.get("commission") != "0.22":
            raise RuntimeError(f"Packaged synthetic fixture result mismatch: {result}")
        paths = [output / f"{base}{suffix}.tar.gz" for suffix in ("", "-source")]
        checksums = []
        for path in paths:
            with path.open("rb") as stream:
                checksums.append(
                    f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {path.name}\n"
                )
        (output / "SHA256SUMS").write_text("".join(checksums))
        print(f"Release archives and SHA256SUMS: {output}")


if __name__ == "__main__":
    main()
