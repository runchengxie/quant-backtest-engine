"""Atomic PAPER account/impact composition with exact source-bound recovery."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace

from .account_events import AccountEventAdapter
from .impact import LinearImpact


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_encoded(value).encode()).hexdigest()


class ExecutionState:
    """All mutable driver state belongs in policy_state, never a hidden closure.

    Admission, cancellation and delivery use the existing event-account API.
    apply_fill accepts an external reference price and adds impact exactly once.
    Copies commit only after account admission and impact updates both succeed.
    """

    def __init__(self, account, impact, *, seed=0, policy_state=None):
        if type(seed) is not int:
            raise ValueError("integer random seed required")
        self.account = account
        self.impact = impact
        self.seed = seed
        self.cursor = 0
        self.policy_state = json.loads(_encoded(policy_state or {}))
        self.applied_fills: dict[str, str] = {}

    def apply_fill(self, event):
        if event.kind != "fill":
            raise ValueError("apply_fill requires a physical fill event")
        fill_id = event.payload.get("fill_id", event.event_id)
        if not isinstance(fill_id, str) or not fill_id:
            raise ValueError("physical fill identity required")
        identity = _digest(
            {
                "occurred_at": event.occurred_at.isoformat(),
                "payload": {k: v for k, v in event.payload.items() if k != "fill_id"},
            }
        )
        previous = self.applied_fills.get(fill_id)
        if previous is not None:
            if previous != identity:
                raise ValueError("physical fill identity reused")
            return
        account = AccountEventAdapter.restore(self.account.checkpoint(), self.account.config)
        impact = LinearImpact.restore(self.impact.checkpoint())
        order = account.pending.get(event.payload["order_id"])
        if order is None:
            raise ValueError("unknown or no longer pending fill order")
        symbol, quantity = order["symbol"], event.payload["quantity"]
        offset = impact.preview(symbol, event.occurred_at.timestamp(), quantity)
        payload = {**event.payload, "price": event.payload["price"] + offset}
        account.apply(replace(event, payload=payload))
        impact.execute(symbol, event.occurred_at.timestamp(), quantity)
        self.account, self.impact = account, impact
        self.applied_fills[fill_id] = identity

    def checkpoint(self):
        if type(self.cursor) is not int or self.cursor < 0:
            raise ValueError("input cursor must be nonnegative integer")
        value = {
            "schema": "execution-state.v2",
            "cursor": self.cursor,
            "seed": self.seed,
            "randomness": "keyed-random.v1",
            "policy_state": deepcopy(self.policy_state),
            "source_binding": self.account.config.source_binding,
            "input_binding": self.account.config.input_binding,
            "account": self.account.checkpoint(),
            "impact": self.impact.checkpoint(),
            "applied_fills": dict(self.applied_fills),
        }
        return {**value, "digest": _digest(value)}

    @classmethod
    def restore(cls, checkpoint, config):
        value = json.loads(_encoded(checkpoint))
        digest = value.pop("digest", None)
        if digest != _digest(value):
            raise ValueError("execution checkpoint digest mismatch")
        if value["schema"] != "execution-state.v2" or value["randomness"] != "keyed-random.v1":
            raise ValueError("unsupported execution state schema")
        if (
            value["source_binding"] != config.source_binding
            or value["input_binding"] != config.input_binding
        ):
            raise ValueError("execution source/input mismatch")
        account = AccountEventAdapter.restore(value["account"], config)
        result = cls(
            account,
            LinearImpact.restore(value["impact"]),
            seed=value["seed"],
            policy_state=value["policy_state"],
        )
        result.cursor = value["cursor"]
        result.applied_fills = value["applied_fills"]
        result.checkpoint()
        return result
