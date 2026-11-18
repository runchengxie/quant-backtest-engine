"""Snapshot, validate, project and execute independent minute scenarios.

No financial arithmetic lives here. Each raw run constructs its own owner;
run_manifest exposes no saved checkpoint, so failures never request one.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from quant_backtest_engine.product import (
    ArtifactRef,
    FailureInfo,
    ProductResult,
    ScenarioIdentity,
    manifest_to_json,
    parse_manifest,
    require_capabilities,
    result_to_json,
)

from ..artifacts import json_bytes, output_paths, read_artifact, resolve_local, write_new
from ..backends.protocol import BackendContext
from ..runner import run_manifest
from .contracts import (
    FAMILIES,
    INPUT_SCHEMA,
    MAX_TARGET_BYTES,
    RECEIPT_FIELDS,
    RECEIPT_SCHEMA,
    PredictionArtifacts,
    PredictionProvider,
    ScenarioAttempt,
    ScenarioCase,
    decode,
    digest,
    plain,
    validate_inputs,
    validate_policy,
    validate_receipt,
    validate_targets,
)


def _no_alias(path: Path) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("scenario paths must not contain symlink aliases")


def _read(ref: ArtifactRef, root: Path, limit: int | None = None) -> bytes:
    if Path(ref.uri).as_posix() != ref.uri:
        raise ValueError("scenario artifact URI must be canonical")
    _no_alias(root / ref.uri)
    if ref.media_type != "application/json":
        raise ValueError("scenario artifacts require application/json")
    if limit is None:
        return read_artifact(ref, root)
    with resolve_local(root, ref.uri).open("rb") as source:
        payload = source.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("target artifact exceeds v1 size limit of 16 MiB")
    if hashlib.sha256(payload).hexdigest() != ref.sha256:
        raise ValueError("artifact digest mismatch: " + ref.uri)
    return payload


def _snapshot(case: ScenarioCase, root: Path) -> dict[str, Any]:
    original: dict[str, Any] = manifest_to_json(case.manifest)
    requested = copy.deepcopy(original)
    identity = plain(case.identity)
    if requested["scenario"] not in (None, identity):
        raise ValueError("case and manifest scenario identities conflict")
    requested["scenario"] = identity
    parse_manifest(requested)
    if case.identity.family not in FAMILIES:
        raise ValueError("unknown scenario family")
    if requested["backend_id"] != "python.minute" or requested["input_schema"] != "minute-input.v1":
        raise ValueError("scenario composition supports only python.minute/minute-input.v1")
    if requested["risk"] is not None:
        raise ValueError("scenario minute profile requires risk=null")
    validate_policy(requested["policy"])
    clocks = requested["clocks"]
    if any(
        clocks[name] is None
        for name in ("available_ns", "information_ns", "decision_ns", "entry_ns")
    ):
        raise ValueError(
            "scenario requires explicit availability/information/decision/entry clocks"
        )
    if (
        not int(clocks["information_ns"])
        <= int(clocks["available_ns"])
        <= int(clocks["decision_ns"])
        <= int(clocks["entry_ns"])
    ):
        raise ValueError("requested scenario clock ordering mismatch")
    resolved = copy.deepcopy(requested)
    captured: list[dict[str, Any]] = []

    def capture(reference: dict[str, Any], pointer: str) -> Any:
        ref = ArtifactRef(**reference)
        raw = _read(ref, root, MAX_TARGET_BYTES if pointer == "/forecast" else None)
        snapshot = ArtifactRef("artifacts/" + ref.sha256 + ".json", ref.sha256, ref.media_type)
        captured.append(
            {
                "pointer": pointer,
                "reference": reference,
                "snapshot": plain(snapshot),
                "sha256": ref.sha256,
                "bytes": raw,
            }
        )
        return decode(raw)

    calendar = capture(requested["calendar"], "/calendar")
    resolved["calendar"] = captured[-1]["snapshot"]
    for name, reference in requested["inputs"].items():
        resolved["inline_inputs"][name] = capture(reference, "/inputs/" + name)
    resolved["inputs"] = {}
    for name, tape in requested["tapes"].items():
        if isinstance(tape, dict):
            resolved["tapes"][name] = capture(tape, "/tapes/" + name)
    if requested["forecast"] is not None:
        capture(requested["forecast"], "/forecast")
    resolved["forecast"] = None
    parse_manifest(resolved)
    envelope = {
        "schema": INPUT_SCHEMA,
        "scenario": identity,
        "prediction_request_sha256": digest(resolved),
        "resolved_manifest": resolved,
        "calendar": calendar,
        "sources": [
            {k: v for k, v in c.items() if k != "bytes"}
            for c in captured
            if c["pointer"] != "/forecast"
        ],
    }
    validate_inputs(envelope)
    return {
        "original": original,
        "requested": requested,
        "envelope": envelope,
        "captured": captured,
    }


def _verify_captured(
    captured: list[dict[str, Any]], original_root: Path, snapshot_root: Path
) -> None:
    for record in captured:
        if _read(ArtifactRef(**record["reference"]), original_root) != record["bytes"]:
            raise ValueError("observed source artifact mutation")
        if _read(ArtifactRef(**record["snapshot"]), snapshot_root) != record["bytes"]:
            raise ValueError("observed source snapshot mutation")


def _callback_source(
    provider: PredictionProvider,
) -> tuple[dict[str, Any], Path | None, bytes | None]:
    cls = type(provider)
    try:
        path = Path(inspect.getfile(cls))
        raw = path.read_bytes()
    except (OSError, TypeError):
        return (
            {
                "status": "unavailable",
                "type": cls.__module__ + "." + cls.__qualname__,
                "sha256": None,
            },
            None,
            None,
        )
    return (
        {
            "status": "verified",
            "type": cls.__module__ + "." + cls.__qualname__,
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        path,
        raw,
    )


def _target(
    reference: ArtifactRef,
    context: BackendContext,
    source_root: Path,
    prediction: PredictionArtifacts,
    case: ScenarioCase,
    envelope: dict[str, Any],
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    raw = _read(reference, context.artifact_root, MAX_TARGET_BYTES)
    saved = ArtifactRef("target.json", hashlib.sha256(raw).hexdigest(), "application/json")
    write_new(source_root / saved.uri, raw)
    record = {
        "reference": plain(reference),
        "snapshot": plain(saved),
        "payload": None,
        "sha256": saved.sha256,
        "source_records_status": "declared",
        "consumed_inputs_status": "unverified",
        "availability_status": "unverified",
        "validation_status": "rejected",
    }
    evidence["target_artifact"] = record
    # Rejected payloads remain exact-byte evidence, never validated execution targets.
    payload = decode(raw)
    record["payload"] = payload
    rows = validate_targets(payload, prediction, case, envelope)
    if (
        _read(reference, context.artifact_root, MAX_TARGET_BYTES) != raw
        or _read(saved, source_root, MAX_TARGET_BYTES) != raw
    ):
        raise ValueError("observed target artifact mutation")
    record.update(
        validation_status="accepted",
        consumed_inputs_status="verified-bytes-and-pointers",
        availability_status="synthetic-bar-close-convention.v1: declared, not observed arrival",
    )
    return rows


def persist_receipt(value: dict[str, Any], root: Path, namespace: str) -> ArtifactRef:
    validate_receipt(value)
    payload = json_bytes(value)
    uri = namespace + "/receipt.json"
    write_new(resolve_local(root, uri), payload)
    return ArtifactRef(uri, hashlib.sha256(payload).hexdigest(), "application/json")


def _receipt(case: ScenarioCase) -> dict[str, Any]:
    result = dict.fromkeys(RECEIPT_FIELDS)
    source_files = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("contracts.py", "runner.py")
    }
    requested = manifest_to_json(case.manifest)
    requested["scenario"] = plain(case.identity)
    result.update(
        schema=RECEIPT_SCHEMA,
        identity=plain(case.identity),
        status="failed",
        stage="snapshot",
        lineage={
            "status": "declared",
            "base_input_sha256": case.identity.base_input_sha256,
            "transformation_sha256": case.identity.transformation_sha256,
            "reason": "No base/transformation payload carriers are supplied",
        },
        checkpoint_scope="unavailable: run_manifest does not expose a saved checkpoint",
        trust="Trusted deterministic per-case callback; not a sandbox or proof against hidden look-ahead",
        adapter={
            "id": "minute-target-projection",
            "version": "v1",
            "source_sha256": digest(source_files),
            "source_files": source_files,
        },
        requested_manifest=requested,
        requested_manifest_sha256=digest(requested),
        projection=[],
        original_manifest=manifest_to_json(case.manifest),
        original_manifest_sha256=digest(manifest_to_json(case.manifest)),
        input_view_projection={
            "removed": ["forecast"],
            "reason": "Output evidence cannot hash its own ArtifactRef; full request and bytes retained separately",
        },
    )
    return result


def _execute(
    case: ScenarioCase,
    snapshot: dict[str, Any],
    context: BackendContext,
    namespace: str,
    evidence: dict[str, Any],
    provider: PredictionProvider | None,
) -> ProductResult:
    sources = context.output_root / namespace / "sources"
    execution = context.output_root / namespace / "execution"
    sources.mkdir()
    execution.mkdir()
    captured = snapshot["captured"]
    for record in captured:
        destination = resolve_local(sources, record["snapshot"]["uri"])
        if not destination.exists():
            write_new(destination, record["bytes"])
    envelope = copy.deepcopy(snapshot["envelope"])
    input_hash = digest(envelope)
    evidence.update(
        original_manifest=snapshot["original"],
        original_manifest_sha256=digest(snapshot["original"]),
        requested_manifest=snapshot["requested"],
        requested_manifest_sha256=digest(snapshot["requested"]),
        callback_inputs=copy.deepcopy(envelope),
        callback_input_sha256=input_hash,
        stage="composition",
    )
    evidence.update(
        prediction_request_manifest=copy.deepcopy(envelope["resolved_manifest"]),
        prediction_request_sha256=envelope["prediction_request_sha256"],
        source_artifacts=[{k: v for k, v in c.items() if k != "bytes"} for c in captured],
    )
    requested_case = ScenarioCase(
        ScenarioIdentity(**plain(case.identity)), parse_manifest(envelope["resolved_manifest"])
    )
    executed = copy.deepcopy(envelope["resolved_manifest"])
    old_targets = copy.deepcopy(executed["inline_inputs"]["targets"])
    prediction = None
    original_prediction = None
    if snapshot["requested"]["forecast"] is not None:
        ref = ArtifactRef(**snapshot["requested"]["forecast"])
        payload = decode(_read(ref, context.artifact_root, MAX_TARGET_BYTES))
        original_prediction = PredictionArtifacts(
            ref,
            None,
            None,
            payload["provider_id"],
            payload["provider_version"],
            payload["available_ns"],
            payload["input_sha256"],
        )
        validate_targets(payload, original_prediction, requested_case, evidence["callback_inputs"])
    if case.identity.forecast_mode == "recomputed":
        if provider is None:
            raise ValueError("recomputed mode requires an explicit trusted callback")
        callback_record, source_path, source_bytes = _callback_source(provider)
        if source_bytes is not None:
            write_new(sources / "callback.py", source_bytes)
            callback_record["snapshot"] = {
                "uri": "callback.py",
                "sha256": hashlib.sha256(source_bytes).hexdigest(),
                "media_type": "text/x-python",
            }
        evidence["callback_source"] = callback_record
        prediction = provider.recompute(requested_case, envelope)
        if (
            plain(requested_case.identity) != evidence["identity"]
            or digest(envelope) != input_hash
            or manifest_to_json(requested_case.manifest) != evidence["prediction_request_manifest"]
        ):
            raise ValueError("observed callback input mutation")
        if source_path is not None and source_path.read_bytes() != source_bytes:
            raise ValueError("observed callback implementation source mutation")
        if not isinstance(prediction, PredictionArtifacts):
            raise ValueError("callback must return PredictionArtifacts")
        if prediction.risk is not None or prediction.forecast is None:
            raise ValueError("recomputed profile requires forecast targets and risk=null")
        policy = (
            snapshot["requested"]["policy"]
            if prediction.policy is None
            else plain(prediction.policy)
        )
        validate_policy(policy)
        executed["policy"] = policy
    elif original_prediction is not None:
        prediction = original_prediction
    if prediction is not None:
        evidence["prediction"] = plain(prediction)
        assert prediction.forecast is not None
        rows = _target(
            prediction.forecast,
            context,
            sources,
            prediction,
            requested_case,
            evidence["callback_inputs"],
            evidence,
        )
        if case.identity.forecast_mode == "fixed" and rows != old_targets:
            raise ValueError("fixed target evidence differs from requested targets")
        executed["inline_inputs"]["targets"] = copy.deepcopy(rows)
    else:
        # The same strict clocks apply to explicit fixed target sensitivity.
        for row in old_targets:
            for name, key in (
                ("information_time", "information_ns"),
                ("decision_time", "decision_ns"),
                ("entry_time", "entry_ns"),
            ):
                if row.get(name) != executed["clocks"][key]:
                    raise ValueError(
                        "fixed targets require explicit matching information/decision/entry clocks"
                    )
    for name in ("scenario", "forecast", "risk"):
        executed[name] = None
    manifest = parse_manifest(executed)
    _verify_captured(captured, context.artifact_root, sources)
    evidence["projection"] = [
        {"field": key, "requested": snapshot["requested"][key], "executed": value}
        for key, value in executed.items()
        if snapshot["requested"][key] != value
    ]
    evidence.update(
        executed_manifest=executed, executed_manifest_sha256=digest(executed), stage="owner"
    )
    from ..backends.minute import MinuteBackend

    owner_context = BackendContext(sources, execution, context.rust_executable, context.rust_sha256)
    require_capabilities(manifest, MinuteBackend(owner_context).descriptor())
    if Path(manifest.output_uri).as_posix() != manifest.output_uri:
        raise ValueError("scenario output URI must be canonical")
    output_paths(manifest.output_uri, owner_context)
    # This is the sole financial invocation. Its fresh owner owns account/policy/impact.
    evidence["owner_call"] = {
        "callable": "quant_backtest_core.runner.run_manifest",
        "manifest_sha256": digest(executed),
        "artifact_root": namespace + "/sources",
        "output_root": namespace + "/execution",
    }
    result = run_manifest(manifest, context=owner_context)
    evidence["owner_result"] = result_to_json(result)
    return result


def run_scenarios(
    cases: Sequence[ScenarioCase],
    *,
    context: BackendContext,
    prediction_provider: PredictionProvider | None = None,
) -> tuple[ScenarioAttempt, ...]:
    """Return ordered attempts, continuing after ordinary failures, never cancellation.

    Use a fresh outer output root for reruns. All case sources are captured before
    any callback is invoked; observed later changes fail instead of changing the run.
    """
    cases = tuple(
        ScenarioCase(
            ScenarioIdentity(**plain(case.identity)),
            parse_manifest(manifest_to_json(case.manifest)),
        )
        for case in cases
    )
    snapshots: list[dict[str, Any] | Exception] = []
    for case in cases:
        try:
            snapshots.append(_snapshot(case, context.artifact_root))
        except Exception as exc:
            snapshots.append(exc)
    attempts: list[ScenarioAttempt] = []
    seen: set[str] = set()
    for case, snapshot in zip(cases, snapshots):
        evidence = _receipt(case)
        result = None
        failure = None
        composition = None
        reserved = False
        namespace = "case-" + digest(plain(case.identity))
        try:
            _no_alias(context.output_root)
            _no_alias(context.artifact_root)
            output, inputs = context.output_root.resolve(), context.artifact_root.resolve()
            if output.is_relative_to(inputs) or inputs.is_relative_to(output):
                raise ValueError("scenario source and output roots must be disjoint")
            if case.identity.id in seen:
                raise ValueError("duplicate scenario id")
            seen.add(case.identity.id)
            context.output_root.mkdir(parents=True, exist_ok=True)
            destination = resolve_local(context.output_root, namespace)
            _no_alias(context.output_root / namespace)
            destination.mkdir(exist_ok=False)
            reserved = True
            if isinstance(snapshot, Exception):
                raise snapshot
            result = _execute(case, snapshot, context, namespace, evidence, prediction_provider)
            evidence.update(status="completed", stage="completed")
        except Exception as exc:
            failure = FailureInfo(
                type(exc).__name__, str(exc) or type(exc).__name__, evidence["stage"], None
            )
            evidence.update(status="failed", failure=plain(failure))
        if reserved:
            try:
                composition = persist_receipt(evidence, context.output_root, namespace)
            except Exception as exc:
                # Preserve an existing original failure. Never fabricate a receipt reference.
                if failure is None:
                    failure = FailureInfo(
                        type(exc).__name__, str(exc) or type(exc).__name__, "receipt", None
                    )
        attempts.append(
            ScenarioAttempt(
                case.identity,
                "failed" if failure else "completed",
                result,
                failure,
                composition=composition,
            )
        )
    return tuple(attempts)
