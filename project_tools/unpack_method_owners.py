"""Unpack only registered release bytes, never arbitrary archive paths."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def unpack(archive: Path, output: Path):
    lock = json.loads(
        (
            Path(__file__).resolve().parents[1] / "docs/assets/method/owner-lock.json"
        ).read_text()
    )
    expected = {**lock["wheels"], "quant-backtest-engine": lock["rust_sha256"]}
    with ZipFile(archive) as source:
        if len(source.namelist()) != len(expected) or set(source.namelist()) != set(
            expected
        ):
            raise ValueError(
                "release archive must contain exactly registered filenames"
            )
        payloads = {name: source.read(name) for name in expected}
    for name, data in payloads.items():
        if hashlib.sha256(data).hexdigest() != expected[name]:
            raise ValueError("unregistered release bytes")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        (output / name).write_bytes(data)
    (output / "quant-backtest-engine").chmod(0o755)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    unpack(a.archive, a.output)
