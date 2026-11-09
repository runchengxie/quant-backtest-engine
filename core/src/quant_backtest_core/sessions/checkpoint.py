"""Provider/source/dependency binding independent of checkpoint-supplied identity."""

from __future__ import annotations

import hashlib
import inspect
import json
import platform
from importlib.metadata import distribution
from pathlib import Path
from typing import Any

from quant_backtest_engine.product import ProviderIdentity

from ..artifacts import _constant, _object, json_bytes
from .protocol import LocalPolicy

SCHEMA = "engine-financial-checkpoint.v1"


def digest(value: Any) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def provider_identity() -> ProviderIdentity:
    import quant_backtest_engine

    roots = {
        "core": Path(__file__).resolve().parents[1],
        "sdk": Path(quant_backtest_engine.__file__).parent,
    }
    sources = {
        f"{name}/{p.relative_to(root).as_posix()}": hashlib.sha256(p.read_bytes()).hexdigest()
        for name, root in roots.items()
        for p in sorted(root.rglob("*.py"))
    }
    dependencies = [("python", platform.python_version())]
    for name in ("quant-backtest-engine-client", "numpy", "pandas", "python-dateutil", "tzdata"):
        dist = distribution(name)
        inventory = {
            str(file): hashlib.sha256(Path(str(dist.locate_file(file))).read_bytes()).hexdigest()
            for file in dist.files or ()
            if not str(file).endswith(".pyc")
            and ".dist-info/" not in str(file)
            and ".data/" not in str(file)
            and Path(str(dist.locate_file(file))).is_file()
        }
        dependencies.extend(((name, dist.version), (name + ":files", digest(inventory))))
    return ProviderIdentity(
        "python.minute",
        "quant-backtest-core",
        distribution("quant-backtest-core").version,
        None,
        digest(sources),
        tuple(dependencies),
    )


def policy_identity(policy: LocalPolicy) -> dict[str, Any]:
    cls = type(policy)
    path = Path(inspect.getfile(cls))
    return {
        "type": cls.__module__ + "." + cls.__qualname__,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "initial_state": policy.state(),
    }


def decode(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload, object_pairs_hook=_object, parse_constant=_constant)
    if not isinstance(value, dict):
        raise ValueError("checkpoint must be an object")
    checksum = value.pop("sha256", None)
    if value.get("schema") != SCHEMA or checksum != digest(value):
        raise ValueError("checkpoint wrapper integrity/schema mismatch")
    if digest(value.get("owner_state")) != value.get("owner_state_sha256"):
        raise ValueError("checkpoint owner integrity mismatch")
    return value
