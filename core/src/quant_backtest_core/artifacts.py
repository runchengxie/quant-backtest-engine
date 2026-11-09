"""Exact-byte local artifacts confined to caller-owned roots; no network access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from quant_backtest_engine.product import ArtifactRef

from .errors import ProductError


def resolve_local(root: Path, uri: str) -> Path:
    parsed = urlsplit(uri)
    if (
        not uri
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or Path(uri).is_absolute()
        or ".." in Path(uri).parts
        or "\\" in uri
    ):
        raise ProductError(f"expected a relative local artifact path: {uri}")
    root = root.resolve()
    target = (root / uri).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ProductError(f"artifact escapes trusted root: {uri}")
    return target


def read_artifact(reference: ArtifactRef, root: Path) -> bytes:
    payload = resolve_local(root, reference.uri).read_bytes()
    if hashlib.sha256(payload).hexdigest() != reference.sha256:
        raise ProductError(f"artifact digest mismatch: {reference.uri}")
    return payload


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProductError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ProductError(f"nonfinite JSON constant: {value}")


def load_artifact(reference: ArtifactRef, root: Path) -> Any:
    if reference.media_type != "application/json":
        raise ProductError("Rust profile artifacts require application/json")
    return json.loads(
        read_artifact(reference, root), object_pairs_hook=_object, parse_constant=_constant
    )


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def output_paths(output_uri: str, context: Any) -> tuple[Path, Path]:
    result = resolve_local(context.output_root, output_uri)
    raw = resolve_local(context.output_root, output_uri + ".native.json")
    for path in (result, raw):
        if any(parent.exists() and not parent.is_dir() for parent in path.parents):
            raise ProductError("output parent must be a directory")
        if path.exists():
            raise ProductError(f"refusing to overwrite existing artifact: {path.name}")
    return result, raw


def write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(payload)
