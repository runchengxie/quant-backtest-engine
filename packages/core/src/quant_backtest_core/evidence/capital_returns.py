# Extracted from quant-platform/packages/platform/src/quant_platform/analytics/capital_returns.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Explicit capital-flow observations; no inferred valuation or unique IRR claim."""

from dataclasses import dataclass
from math import fsum, isclose, isfinite, prod, ulp


@dataclass(frozen=True)
class CapitalObservation:
    at_ns: int
    nav_before_flow: float
    external_flow: float
    nav_after_flow: float


def _number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("finite numeric capital observation required")
    if positive and value <= 0:
        raise ValueError("positive capital series required; full redemption is a boundary")
    return float(value)


def capital_performance(initial_nav, start_ns, observations):
    initial = _number(initial_nav, positive=True)
    if type(start_ns) is not int:
        raise ValueError("integer UTC ns clock required")
    observations = tuple(observations)
    if not observations:
        raise ValueError("nonempty complete capital observations required")
    previous = initial
    clock = start_ns
    ratios = []
    flows = []
    for row in observations:
        if type(row.at_ns) is not int or row.at_ns <= clock:
            raise ValueError("strictly increasing integer clock required")
        before = _number(row.nav_before_flow, positive=True)
        after = _number(row.nav_after_flow, positive=True)
        flow = _number(row.external_flow)
        if not isclose(
            after,
            before + flow,
            rel_tol=0,
            abs_tol=max(8 * ulp(after), 8 * ulp(before + flow)),
        ):
            raise ValueError("capital flow identity violated")
        ratios.append(before / previous)
        flows.append(flow)
        previous, clock = after, row.at_ns
    total_flow = fsum(flows)
    gain = fsum((previous, -initial, -total_flow))
    denominator = fsum(
        [
            initial,
            *(
                f * (clock - r.at_ns) / (clock - start_ns)
                for r, f in zip(observations, flows, strict=True)
            ),
        ]
    )
    linked = prod(ratios) - 1
    if not all(isfinite(x) for x in (total_flow, gain, denominator, linked)):
        raise ValueError("capital arithmetic overflow")
    return {
        "schema": "capital-performance.v1",
        "time_weighted_return": linked,
        "net_external_flow": total_flow,
        "net_monetary_gain": gain,
        "modified_dietz_return": gain / denominator if denominator > 0 else None,
        "dietz_basis": "approximate_elapsed_time_weighted_external_flows",
        "money_weighted_irr": None,
        "irr_status": "not_estimated_no_unique_root_claim",
        "valuation_requirement": "complete_before_and_after_each_external_flow",
    }
