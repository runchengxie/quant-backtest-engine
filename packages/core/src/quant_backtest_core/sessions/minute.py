"""A single-owner session facade; failure retains the last successful checkpoint."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from quant_backtest_engine.product import ProductManifest, ProductResult, manifest_to_json

from ..artifacts import json_bytes
from ..backends.minute import prepare
from ..backends.protocol import BackendContext
from .checkpoint import SCHEMA, decode, digest, policy_identity
from .policies import PolicyBridge, select_policy
from .protocol import LocalPolicy, SessionObservation
from .results import normalize, transport


class MinuteFinancialSession:
    def __init__(
        self, manifest: ProductManifest, context: BackendContext, policy: LocalPolicy | None
    ) -> None:
        kwargs, inputs, self.provider = prepare(manifest, context)
        from ..backtest.minute_session import MinuteSession

        self.manifest, self.context = manifest, context
        self.policy = select_policy(manifest, policy)
        self.manifest_hash = digest(manifest_to_json(manifest))
        self.binding = digest(
            {
                "manifest": manifest_to_json(manifest),
                "inputs": inputs,
                "provider": self._provider_wire(),
                "policy": policy_identity(self.policy),
            }
        )
        self.bridge = PolicyBridge(self.policy)
        self.owner = MinuteSession(**kwargs, policy=self.bridge)
        self.failure: Exception | None = None
        self.result: ProductResult | None = None
        self.last_successful_checkpoint = self._checkpoint()
        self._observation = self._observe()

    def _provider_wire(self) -> dict[str, Any]:
        # ProviderIdentity contains only scalars and pairs, avoiding mappingproxy deepcopy.
        return {
            "backend_id": self.provider.backend_id,
            "distribution": self.provider.distribution,
            "version": self.provider.version,
            "source_revision": self.provider.source_revision,
            "source_sha256": self.provider.source_sha256,
            "dependencies": dict(self.provider.dependencies),
            "artifact_sha256": self.provider.artifact_sha256,
        }

    def _healthy(self) -> None:
        if self.failure is not None:
            raise self.failure

    def _observe(self) -> SessionObservation:
        time = self.owner.simulation.times[self.owner.cursor - 1] if self.owner.cursor else None
        start = self.manifest.clocks.available_ns
        if start is None:
            start = str(self.owner.simulation.times[0].value)
        account = transport(self.owner.delivered)
        return SessionObservation(
            self.owner.cursor,
            str(time.value) if time is not None else start,
            account,
            tuple(account["pending_orders"]),
        )

    def observe(self) -> SessionObservation:
        return self._observation

    def step(self) -> SessionObservation | None:
        self._healthy()
        if self.result is not None:
            raise ValueError("session already finished")
        try:
            self.bridge.cursor = self.owner.cursor
            if not self.owner.step():
                return None
            observation = self._observe()
            checkpoint = self._checkpoint()
            self._observation = observation
            self.last_successful_checkpoint = checkpoint
            return observation
        except Exception as exc:
            self.failure = exc
            raise

    def _checkpoint(self) -> bytes:
        state = self.owner.checkpoint()
        value = {
            "schema": SCHEMA,
            "provider": self._provider_wire(),
            "input_schema": self.manifest.input_schema,
            "manifest_sha256": self.manifest_hash,
            "binding_sha256": self.binding,
            "cursor": self.owner.cursor,
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.version,
            "policy_state_schema": self.policy.state_schema,
            "owner_schema": "minute-session.v3",
            "owner_state": state,
            "owner_state_sha256": digest(state),
        }
        return json_bytes({**value, "sha256": digest(value)})

    def checkpoint(self) -> bytes:
        self._healthy()
        if self.result is not None:
            raise ValueError("cannot checkpoint a finished session")
        return self.last_successful_checkpoint

    def finish(self) -> ProductResult:
        self._healthy()
        if self.result is not None:
            return self.result
        try:
            while self.step() is not None:
                pass
            native = self.owner.run()
            self.result = normalize(
                native, self.manifest, self.provider, self.manifest_hash, self.context
            )
            return self.result
        except Exception as exc:
            self.failure = exc
            raise

    def restore(self, payload: bytes) -> None:
        value = decode(payload)
        expected = decode(self.last_successful_checkpoint)
        for key in expected.keys() - {"cursor", "owner_state", "owner_state_sha256"}:
            if value.get(key) != expected[key]:
                raise ValueError(f"checkpoint binding mismatch: {key}")
        if set(value) != set(expected):
            raise ValueError("checkpoint fields mismatch")
        state = value["owner_state"]
        if value["cursor"] != state["cursor"]:
            raise ValueError("checkpoint cursor mismatch")
        # Both the expected delay and all tape/model inputs came from the manifest.
        if state["delay"] != self.owner.delay:
            raise ValueError("checkpoint delay mismatch")
        expected_impact = self.owner.simulation.impact_model
        if (state["impact"] is None) != (expected_impact is None):
            raise ValueError("checkpoint impact mismatch")
        if expected_impact is not None:
            for key in ("transient", "permanent", "decay_seconds"):
                if state["impact"][key] != getattr(expected_impact, key):
                    raise ValueError("checkpoint impact config mismatch")
        if state["quantity_locks"] != [asdict(lock) for lock in self.owner.quantity_locks]:
            # JSON arrays represent the exact tuple-valued symbols.
            if json_bytes(state["quantity_locks"]) != json_bytes(
                [asdict(lock) for lock in self.owner.quantity_locks]
            ):
                raise ValueError("checkpoint locks mismatch")
        self.policy.restore_state(state["policy"])
        from ..backtest.minute_session import MinuteSession

        self.owner = MinuteSession.restore(
            self.owner.targets,
            self.owner.bars,
            self.owner.config,
            state,
            policy=self.bridge,
            **self.owner.tapes,
        )
        self.bridge.cursor = self.owner.cursor
        self.last_successful_checkpoint = self._checkpoint()
        self._observation = self._observe()
