"""Synthetic independent hand oracle; installed wheels, actual financial owner."""

import copy
import hashlib
import importlib.util
import json
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from quant_backtest_engine.product import (
    ArtifactRef,
    ScenarioIdentity,
    parse_manifest,
    result_to_json,
)

from quant_backtest_core import BackendContext
from quant_backtest_core.artifacts import json_bytes

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "1767576540000000000"  # 2026-01-05 09:29 Asia/Shanghai
DECISION = "1767576600000000000"  # 09:30
ENTRY = "1767576660000000000"  # 09:31
FILL = "1767576780000000000"  # 09:33, interval 09:32:30 > entry + 1 minute latency


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def artifact(root, name, value):
    data = json_bytes(value)
    (root / name).write_bytes(data)
    return ArtifactRef(name, hashlib.sha256(data).hexdigest(), "application/json")


def fixture(tmp_path, identifier="A", close="9", mode="recomputed", seed=1):
    from quant_backtest_core.scenarios import ScenarioCase

    sources = tmp_path / "inputs"
    sources.mkdir(exist_ok=True)
    calendar = artifact(
        sources,
        "calendar.json",
        {
            "schema": "synthetic-calendar.v1",
            "timezone": "Asia/Shanghai",
            "sessions": ["2026-01-05"],
        },
    )
    wire = json.loads((ROOT / "fixtures/product/minute-session.json").read_text())
    row = wire["inline_inputs"]["bars"][0]
    bars = []
    for instant, price in [(PREFIX, close), (DECISION, "10"), (FILL, "10")]:
        bar = copy.deepcopy(row)
        bar.update(
            time=instant,
            interval_start=str(int(instant) - 30_000_000_000),
            open=price,
            high=price,
            low=price,
            close=price,
            amount=str(int(price) * 1000),
            up_limit="20",
            down_limit="1",
            volume="1000",
        )
        bars.append(bar)
    wire["inline_inputs"] = {
        "bars": bars,
        "targets": [
            {
                "information_time": PREFIX,
                "decision_time": DECISION,
                "entry_time": ENTRY,
                "symbol": "A",
                "weight": "0",
            }
        ],
    }
    wire["calendar"] = asdict(calendar)
    wire["initial_account"] = {"cash": "1000"}
    wire["tapes"] = {key: [] for key in wire["tapes"]}
    wire["settings"]["config"].update(
        participation_rate="1",
        buy_fee_bp="0",
        sell_fee_bp="0",
        commission_minimum_cny="0",
        sell_tax_bp="0",
        lot_size=1,
        latency_minutes=1,
    )
    wire["settings"].update(impact=None, report_delay_seconds="0")
    wire["clocks"].update(
        available_ns=PREFIX, information_ns=PREFIX, decision_ns=DECISION, entry_ns=ENTRY
    )
    wire["required_capabilities"] = ["session_ledger"]
    identity = ScenarioIdentity(identifier, "external-market-path", seed, "1" * 64, "2" * 64, mode)
    return ScenarioCase(identity, parse_manifest(wire)), BackendContext(
        sources, tmp_path / "outputs"
    )


class PrefixProvider:
    def __init__(self, root, mutate=None):
        self.root, self.mutate = root, mutate
        self.seen = []

    def recompute(self, case, inputs):
        from quant_backtest_core.scenarios import PredictionArtifacts

        self.seen.append(case.identity.id)
        source = inputs["resolved_manifest"]["inline_inputs"]["bars"][0]
        targets = copy.deepcopy(inputs["resolved_manifest"]["inline_inputs"]["targets"])
        targets[0]["weight"] = "1" if Decimal(source["close"]) > 10 else "0"
        payload = {
            "schema": "scenario-minute-targets.v1",
            "scenario": asdict(case.identity),
            "provider_id": "synthetic-prefix",
            "provider_version": "v1",
            "available_ns": PREFIX,
            "input_sha256": digest(inputs),
            "targets": targets,
            "source_records": [
                {
                    "id": "synthetic-rule",
                    "kind": "implementation",
                    "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                }
            ],
            "consumed_inputs": [
                {
                    "pointer": "/resolved_manifest/inline_inputs/bars/0",
                    "sha256": digest(source),
                    "available_ns": PREFIX,
                }
            ],
        }
        if self.mutate:
            self.mutate(case, inputs, payload)
        forecast = artifact(self.root, case.identity.id + ".json", payload)
        return PredictionArtifacts(
            forecast,
            None,
            None,
            payload["provider_id"],
            payload["provider_version"],
            payload["available_ns"],
            payload["input_sha256"],
        )


def receipt(attempt, context):
    assert attempt.composition is not None
    data = (context.output_root / attempt.composition.uri).read_bytes()
    assert hashlib.sha256(data).hexdigest() == attempt.composition.sha256
    return json.loads(data)


def table(result, name):
    return next(t.rows for t in result.tables if t.name == name)


def test_independent_scenario_runner_exists():
    assert importlib.util.find_spec("quant_backtest_core.scenarios") is not None


def test_actual_recomputed_orders_fills_and_fixed_control(tmp_path):
    from quant_backtest_core.runner import run_manifest
    from quant_backtest_core.scenarios import run_scenarios

    a, context = fixture(tmp_path)
    bad, _ = fixture(tmp_path, "bad", "11", seed=2)
    b, _ = fixture(tmp_path, "B", "11", seed=3)
    fixed, _ = fixture(tmp_path, "fixed", "11", mode="fixed", seed=4)

    def middle(case, inputs, payload):
        if case.identity.id == "bad":
            payload["schema"] = "opaque-forecast.v1"

    provider = PrefixProvider(context.artifact_root, middle)
    with patch("quant_backtest_core.scenarios.runner.run_manifest", wraps=run_manifest) as owner:
        attempts = run_scenarios([a, bad, b, fixed], context=context, prediction_provider=provider)
    assert [a.status for a in attempts] == ["completed", "failed", "completed", "completed"]
    assert owner.call_count == 3
    assert provider.seen == ["A", "bad", "B"]
    assert table(attempts[0].result, "fills") == ()
    assert table(attempts[3].result, "fills") == ()
    (fill,) = table(attempts[2].result, "fills")
    assert fill["side"] == "buy"
    assert Decimal(fill["quantity"]) == 100
    assert Decimal(fill["price"]) == 10
    daily = table(attempts[2].result, "daily")[-1]
    assert Decimal(daily["cash"]) == 0
    assert Decimal(table(attempts[2].result, "positions")[-1]["quantity"]) == 100
    assert Decimal(table(attempts[0].result, "daily")[-1]["cash"]) == 1000
    assert table(attempts[2].result, "reports")
    for index, attempt in enumerate(attempts):
        evidence = receipt(attempt, context)
        assert evidence["status"] == attempt.status
        assert evidence["original_manifest"]["scenario"] is None
        assert evidence["requested_manifest"]["scenario"] == asdict(attempt.identity)
        assert evidence["lineage"]["status"] == "declared"
        assert evidence["last_successful_checkpoint"] is None
        if attempt.result is None:
            assert evidence["owner_call"] is None
            continue
        executed = evidence["executed_manifest"]
        assert executed["scenario"] is executed["forecast"] is executed["risk"] is None
        assert attempt.result.manifest_sha256 == digest(executed)
        assert attempt.result.scenario is None
        expected = "1" if index == 2 else "0"
        assert executed["inline_inputs"]["targets"][0]["weight"] == expected
        assert executed["initial_account"] == {"cash": "1000"}
        assert executed["required_capabilities"] == ["session_ledger"]
        output = context.output_root / evidence["owner_call"]["output_root"]
        assert (output / executed["output_uri"]).read_bytes() == json_bytes(
            result_to_json(attempt.result)
        )
        assert (
            hashlib.sha256((output / attempt.result.raw_result.uri).read_bytes()).hexdigest()
            == attempt.result.raw_result.sha256
        )
        # A direct new owner on the exact projected snapshot produces the complete same result.
        direct = run_manifest(
            parse_manifest(executed),
            context=BackendContext(
                context.output_root / evidence["owner_call"]["artifact_root"],
                tmp_path / ("direct-" + str(index)),
            ),
        )
        assert result_to_json(direct) == result_to_json(attempt.result)


@pytest.mark.parametrize(
    "change",
    ["input", "scenario", "source", "late", "mutation", "unknown", "risk", "policy", "clock"],
)
def test_rejects_before_owner(tmp_path, change):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)

    def mutate(case, inputs, payload):
        if change == "input":
            payload["input_sha256"] = "0" * 64
        if change == "scenario":
            payload["scenario"]["id"] = "other"
        if change == "source":
            payload["consumed_inputs"][0]["sha256"] = "0" * 64
        if change == "late":
            payload["available_ns"] = str(int(DECISION) + 1)
        if change == "mutation":
            inputs["resolved_manifest"]["inline_inputs"]["bars"][0]["close"] = "12"
        if change == "unknown":
            payload["surprise"] = "opaque"
        if change == "clock":
            payload["targets"][0]["information_time"] = int(PREFIX)

    provider = PrefixProvider(context.artifact_root, mutate)
    if change in ("risk", "policy"):
        original = provider.recompute

        def recompute(case, inputs):
            value = original(case, inputs)
            if change == "risk":
                return replace(value, risk=value.forecast)
            from quant_backtest_engine.product import PolicyRef

            return replace(value, policy=PolicyRef("unknown", "v1", "unknown.v1", {}))

        provider.recompute = recompute
    with patch("quant_backtest_core.scenarios.runner.run_manifest") as owner:
        (attempt,) = run_scenarios([case], context=context, prediction_provider=provider)
    assert attempt.status == "failed"
    owner.assert_not_called()
    assert receipt(attempt, context)["owner_call"] is None


def test_missing_callback_fixed_evidence_conflicts_and_duplicate_outputs(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)
    (failed,) = run_scenarios([case], context=context)
    assert failed.status == "failed"
    retained = (context.output_root / failed.composition.uri).read_bytes()
    (collided,) = run_scenarios(
        [case], context=context, prediction_provider=PrefixProvider(context.artifact_root)
    )
    assert collided.status == "failed" and collided.composition is None
    assert (context.output_root / failed.composition.uri).read_bytes() == retained


def test_changed_source_bytes_are_rejected(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)

    def mutate(case, inputs, payload):
        (context.artifact_root / "calendar.json").write_bytes(b"{}")

    with patch("quant_backtest_core.scenarios.runner.run_manifest") as owner:
        (attempt,) = run_scenarios(
            [case],
            context=context,
            prediction_provider=PrefixProvider(context.artifact_root, mutate),
        )
    assert attempt.status == "failed"
    owner.assert_not_called()


def test_cancellation_propagates_and_persistence_failure_has_no_fictional_ref(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)

    def cancel(case, inputs, payload):
        raise KeyboardInterrupt("cancel")

    with pytest.raises(KeyboardInterrupt):
        run_scenarios(
            [case],
            context=context,
            prediction_provider=PrefixProvider(context.artifact_root, cancel),
        )
    context = replace(context, output_root=tmp_path / "second")
    with patch(
        "quant_backtest_core.scenarios.runner.persist_receipt",
        side_effect=OSError("storage failed"),
    ):
        (attempt,) = run_scenarios([case], context=context)
    assert attempt.status == "failed" and attempt.composition is None
    assert "callback" in attempt.failure.message


def test_reordering_reproduces_complete_financial_results(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    a, context = fixture(tmp_path)
    b, _ = fixture(tmp_path, "B", "11", seed=2)
    first = run_scenarios(
        [a, b], context=context, prediction_provider=PrefixProvider(context.artifact_root)
    )
    other = replace(context, output_root=tmp_path / "rerun")
    second = run_scenarios(
        [b, a], context=other, prediction_provider=PrefixProvider(context.artifact_root)
    )
    assert all(attempt.status == "completed" for attempt in first + second)
    assert [result_to_json(x.result) for x in first] == [
        result_to_json(x.result) for x in reversed(second)
    ]


def test_fixed_typed_evidence_has_no_self_reference_and_preserves_full_request(tmp_path):
    from quant_backtest_engine.product import manifest_to_json

    from quant_backtest_core.scenarios import ScenarioCase, run_scenarios

    case, context = fixture(tmp_path, mode="fixed")
    (baseline,) = run_scenarios([case], context=context)
    original = receipt(baseline, context)
    envelope = original["callback_inputs"]
    view = ScenarioCase(case.identity, parse_manifest(envelope["resolved_manifest"]))
    evidence = PrefixProvider(context.artifact_root).recompute(view, envelope)
    request = manifest_to_json(case.manifest)
    request["forecast"] = asdict(evidence.forecast)
    attached = ScenarioCase(case.identity, parse_manifest(request))
    new_context = replace(context, output_root=tmp_path / "attached")
    (attempted,) = run_scenarios([attached], context=new_context)
    assert attempted.status == "completed", attempted.failure
    full = receipt(attempted, new_context)
    assert full["callback_input_sha256"] == original["callback_input_sha256"]
    assert full["requested_manifest_sha256"] != original["requested_manifest_sha256"]
    assert full["source_artifacts"][-1]["reference"] == asdict(evidence.forecast)
    assert full["target_artifact"]["availability_status"].startswith(
        "synthetic-bar-close-convention.v1: declared"
    )
    assert full["target_artifact"]["source_records_status"] == "declared"
    # A different forecast filename changes full request binding, never the prediction domain.
    (context.artifact_root / "alias.json").write_bytes(
        (context.artifact_root / evidence.forecast.uri).read_bytes()
    )
    request["forecast"]["uri"] = "alias.json"
    alias_context = replace(context, output_root=tmp_path / "alias-output")
    (alias,) = run_scenarios(
        [ScenarioCase(case.identity, parse_manifest(request))], context=alias_context
    )
    assert alias.status == "completed", alias.failure
    aliased = receipt(alias, alias_context)
    assert aliased["callback_input_sha256"] == full["callback_input_sha256"]
    assert aliased["requested_manifest_sha256"] != full["requested_manifest_sha256"]
    request["inline_inputs"]["bars"][0]["close"] = "8"
    changed_context = replace(context, output_root=tmp_path / "changed")
    (changed,) = run_scenarios(
        [ScenarioCase(case.identity, parse_manifest(request))], context=changed_context
    )
    assert changed.status == "failed"
    assert (
        receipt(changed, changed_context)["callback_input_sha256"] != full["callback_input_sha256"]
    )


def test_callback_case_is_the_bound_prediction_view(tmp_path):
    from quant_backtest_engine.product import manifest_to_json

    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)

    def validate(case, inputs, payload):
        assert manifest_to_json(case.manifest) == inputs["resolved_manifest"]
        assert digest(manifest_to_json(case.manifest)) == inputs["prediction_request_sha256"]

    (attempted,) = run_scenarios(
        [case], context=context, prediction_provider=PrefixProvider(context.artifact_root, validate)
    )
    assert attempted.status == "completed"


@pytest.mark.parametrize(
    "variant",
    [
        "future-source",
        "bad-pointer",
        "source-clock",
        "missing-mode",
        "identity",
        "backend",
        "capability",
        "traversal",
        "output-symlink",
        "source-symlink",
    ],
)
def test_contract_and_namespace_failures_never_dispatch_owner(tmp_path, variant):
    from quant_backtest_engine.product import manifest_to_json

    from quant_backtest_core.scenarios import ScenarioCase, run_scenarios

    case, context = fixture(tmp_path)
    wire = manifest_to_json(case.manifest)
    if variant == "missing-mode":
        with pytest.raises(ValueError):
            replace(case.identity, forecast_mode=None)
        return
    if variant == "identity":
        wire["scenario"] = asdict(replace(case.identity, id="other"))
    if variant == "backend":
        wire["backend_id"] = "rust.nautilus.sessions"
    if variant == "capability":
        wire["required_capabilities"] += ["unsupported"]
    if variant == "traversal":
        wire["output_uri"] = "../receipt.json"
    if variant == "output-symlink":
        (tmp_path / "outside").mkdir()
        context.output_root.symlink_to(tmp_path / "outside", target_is_directory=True)
    if variant == "source-symlink":
        (context.artifact_root / "original.json").write_bytes(
            (context.artifact_root / "calendar.json").read_bytes()
        )
        (context.artifact_root / "calendar.json").unlink()
        (context.artifact_root / "calendar.json").symlink_to(
            context.artifact_root / "original.json"
        )
    case = ScenarioCase(case.identity, parse_manifest(wire))

    def mutate(case, inputs, payload):
        item = payload["consumed_inputs"][0]
        if variant == "future-source":
            item.update(
                pointer="/resolved_manifest/inline_inputs/bars/2",
                sha256=digest(inputs["resolved_manifest"]["inline_inputs"]["bars"][2]),
                available_ns=FILL,
            )
        if variant == "bad-pointer":
            item["pointer"] = "/resolved_manifest/inline_inputs/bars/01"
        if variant == "source-clock":
            item["available_ns"] = str(int(PREFIX) - 1)

    with patch("quant_backtest_core.scenarios.runner.run_manifest") as owner:
        (attempt,) = run_scenarios(
            [case],
            context=context,
            prediction_provider=PrefixProvider(context.artifact_root, mutate),
        )
    assert attempt.status == "failed"
    owner.assert_not_called()


def test_duplicate_identity_and_owner_failure_continue_without_checkpoint(tmp_path):
    from quant_backtest_core.runner import run_manifest
    from quant_backtest_core.scenarios import run_scenarios

    a, context = fixture(tmp_path)
    b, _ = fixture(tmp_path, "B", "11", seed=2)
    error = RuntimeError("original financial error")

    def execute(manifest, *, context):
        if manifest.inline_inputs["targets"][0]["weight"] == "0":
            raise error
        return run_manifest(manifest, context=context)

    with patch("quant_backtest_core.scenarios.runner.run_manifest", side_effect=execute) as owner:
        first, duplicate, last = run_scenarios(
            [a, a, b], context=context, prediction_provider=PrefixProvider(context.artifact_root)
        )
    assert first.failure.message == str(error)
    assert first.failure.code == "RuntimeError" and first.failure.stage == "owner"
    assert duplicate.status == "failed" and duplicate.composition is None
    assert last.status == "completed" and owner.call_count == 2
    assert receipt(first, context)["last_successful_checkpoint"] is None


def test_fresh_financial_accounts_policies_and_impact_instances(tmp_path):
    from quant_backtest_engine.product import manifest_to_json

    from quant_backtest_core.scenarios import ScenarioCase, run_scenarios
    from quant_backtest_core.sessions.minute import MinuteFinancialSession

    cases = []
    for name, seed in (("A", 1), ("B", 2)):
        case, context = fixture(tmp_path, name, "11", seed=seed)
        wire = manifest_to_json(case.manifest)
        wire["model_versions"] = {"linear-impact": "v1"}
        wire["settings"]["impact"] = {"transient": "0.001", "permanent": "0", "decay_seconds": "60"}
        cases.append(ScenarioCase(case.identity, parse_manifest(wire)))
    owners = []
    original = MinuteFinancialSession.__init__

    def capture(self, *args, **kwargs):
        original(self, *args, **kwargs)
        owners.append(self)

    with patch.object(MinuteFinancialSession, "__init__", capture):
        attempts = run_scenarios(
            cases, context=context, prediction_provider=PrefixProvider(context.artifact_root)
        )
    assert all(a.status == "completed" for a in attempts)
    assert len(owners) == 2
    for attempt in attempts:
        (fill,) = table(attempt.result, "fills")
        assert fill["quantity"] == "99" and fill["price"] == "10.0495"
        assert table(attempt.result, "daily")[-1]["cash"] == "5.099500000000035"
    for owner in owners:
        assert owner.owner.simulation.impact_model.checkpoint()["states"]["A"]["transient"] == 0.099
    for accessor in (
        lambda s: s.owner,
        lambda s: s.policy,
        lambda s: s.bridge,
        lambda s: s.owner.simulation,
        lambda s: s.owner.simulation.impact_model,
    ):
        assert accessor(owners[0]) is not accessor(owners[1])
    assert (
        owners[0].owner.simulation.impact_model.checkpoint()
        == owners[1].owner.simulation.impact_model.checkpoint()
    )
    assert result_to_json(attempts[0].result) == result_to_json(attempts[1].result)


def test_fixed_different_targets_and_changed_returned_bytes_fail(tmp_path):
    from quant_backtest_engine.product import manifest_to_json

    from quant_backtest_core.scenarios import ScenarioCase, run_scenarios

    case, context = fixture(tmp_path, mode="fixed")
    (first,) = run_scenarios([case], context=context)
    envelope = receipt(first, context)["callback_inputs"]

    def change(case, inputs, payload):
        payload["targets"][0]["weight"] = "1"

    evidence = PrefixProvider(context.artifact_root, change).recompute(case, envelope)
    wire = manifest_to_json(case.manifest)
    wire["forecast"] = asdict(evidence.forecast)
    with patch("quant_backtest_core.scenarios.runner.run_manifest") as owner:
        (mismatch,) = run_scenarios(
            [ScenarioCase(case.identity, parse_manifest(wire))],
            context=replace(context, output_root=tmp_path / "mismatch"),
        )
    assert mismatch.status == "failed" and "fixed target" in mismatch.failure.message
    owner.assert_not_called()
    (context.artifact_root / evidence.forecast.uri).write_bytes(b"{}")
    with patch("quant_backtest_core.scenarios.runner.run_manifest") as owner:
        (changed,) = run_scenarios(
            [ScenarioCase(case.identity, parse_manifest(wire))],
            context=replace(context, output_root=tmp_path / "changed-bytes"),
        )
    assert changed.status == "failed" and "digest mismatch" in changed.failure.message
    owner.assert_not_called()


def test_successful_owner_and_failed_receipt_retains_actual_result(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path, mode="fixed")
    with patch(
        "quant_backtest_core.scenarios.runner.persist_receipt",
        side_effect=OSError("receipt storage failed"),
    ):
        (attempt,) = run_scenarios([case], context=context)
    assert attempt.status == "failed" and attempt.result.status == "completed"
    assert attempt.composition is None and attempt.failure.stage == "receipt"
    assert attempt.failure.message == "receipt storage failed"


def test_callback_case_identity_mutation_is_observed_without_mutating_caller(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)

    def mutate(callback_case, inputs, payload):
        object.__setattr__(callback_case.identity, "id", "mutated")

    with patch("quant_backtest_core.scenarios.runner.run_manifest") as owner:
        (attempt,) = run_scenarios(
            [case],
            context=context,
            prediction_provider=PrefixProvider(context.artifact_root, mutate),
        )
    assert attempt.status == "failed"
    assert case.identity.id == attempt.identity.id == "A"
    assert "mutation" in attempt.failure.message
    owner.assert_not_called()


def test_typed_artifact_rejects_boolean_identity_seed(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)

    def mutate(case, inputs, payload):
        payload["scenario"]["seed"] = True

    with patch("quant_backtest_core.scenarios.runner.run_manifest") as owner:
        (attempt,) = run_scenarios(
            [case],
            context=context,
            prediction_provider=PrefixProvider(context.artifact_root, mutate),
        )
    assert attempt.status == "failed"
    owner.assert_not_called()


def test_rejected_target_exact_bytes_survive_in_case_evidence(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)

    def opaque(case, inputs, payload):
        payload["schema"] = "opaque.v1"

    (attempt,) = run_scenarios(
        [case], context=context, prediction_provider=PrefixProvider(context.artifact_root, opaque)
    )
    assert attempt.status == "failed"
    evidence = receipt(attempt, context)
    target = evidence["target_artifact"]
    assert target is not None
    assert target["validation_status"] == "rejected"
    assert target["consumed_inputs_status"] == "unverified"
    snapshot = (
        context.output_root
        / Path(attempt.composition.uri).parent
        / "sources"
        / target["snapshot"]["uri"]
    )
    assert (
        snapshot.read_bytes() == (context.artifact_root / target["reference"]["uri"]).read_bytes()
    )
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == target["sha256"]
    assert evidence["owner_call"] is None


def test_target_artifact_size_is_bounded_before_owner_dispatch(tmp_path):
    from quant_backtest_core.scenarios import run_scenarios

    case, context = fixture(tmp_path)
    provider = PrefixProvider(context.artifact_root)
    original = provider.recompute

    def oversized(case, inputs):
        prediction = original(case, inputs)
        path = context.artifact_root / prediction.forecast.uri
        data = path.read_bytes() + b" " * (16 * 1024 * 1024)
        path.write_bytes(data)
        return replace(
            prediction,
            forecast=replace(prediction.forecast, sha256=hashlib.sha256(data).hexdigest()),
        )

    provider.recompute = oversized
    from quant_backtest_core.runner import run_manifest

    with patch("quant_backtest_core.scenarios.runner.run_manifest", wraps=run_manifest) as owner:
        (attempt,) = run_scenarios([case], context=context, prediction_provider=provider)
    assert attempt.status == "failed"
    owner.assert_not_called()
    assert "size" in attempt.failure.message
