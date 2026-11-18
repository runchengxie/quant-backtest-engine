"""Fixed resumable policy registry plus an explicitly trusted local object bridge."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from quant_backtest_engine.product import JsonValue, ProductManifest

from .protocol import LocalPolicy, SessionObservation


class TargetWeights:
    policy_id = "target-weights"
    version = "v1"
    state_schema = "target-weights-state.v1"

    def decide(self, observation: SessionObservation) -> Mapping[str, str]:
        return cast(Mapping[str, str], observation.account["proposed_weights"])

    def state(self) -> JsonValue:
        return {}

    def restore_state(self, state: JsonValue) -> None:
        if state != {}:
            raise ValueError("invalid target-weights policy state")


def select_policy(manifest: ProductManifest, policy: LocalPolicy | None) -> LocalPolicy:
    ref = manifest.policy
    if ref is None:
        raise ValueError("minute requires an explicit policy identity")
    if policy is None:
        if (ref.id, ref.version, ref.state_schema, dict(ref.config)) != (
            "target-weights",
            "v1",
            "target-weights-state.v1",
            {},
        ):
            raise ValueError("only fixed target-weights.v1 is remotely resumable")
        policy = TargetWeights()
    if (policy.policy_id, policy.version, policy.state_schema) != (
        ref.id,
        ref.version,
        ref.state_schema,
    ):
        raise ValueError("local policy identity differs from manifest")
    return policy


class PolicyBridge:
    def __init__(self, policy: LocalPolicy) -> None:
        self.policy = policy
        self.cursor = 0

    def __call__(self, state: Any, proposed: Any) -> Any:
        from .results import transport

        observation = SessionObservation(
            self.cursor,
            str(state.time.value),
            transport(
                {
                    "cash": state.cash,
                    "nav": state.nav,
                    "holdings": dict(state.holdings),
                    "cash_receivable": state.cash_receivable,
                    "stock_receivable_value": state.stock_receivable_value,
                    "marks": dict(state.marks),
                    "proposed_weights": proposed,
                }
            ),
            tuple(transport(dict(order)) for order in state.pending_orders),
        )
        weights = self.policy.decide(observation)
        if not isinstance(weights, Mapping):
            raise ValueError("policy must return decimal target weights")
        from quant_backtest_engine.product.validation import _decimal

        for symbol, weight in weights.items():
            if not isinstance(symbol, str):
                raise ValueError("policy symbols must be strings")
            _decimal(weight, "weight")
        # Preserve the existing pending-order gate, including delayed-report sentinel.
        return None if state.pending_orders else {s: float(w) for s, w in weights.items()}

    def checkpoint(self) -> JsonValue:
        return self.policy.state()
