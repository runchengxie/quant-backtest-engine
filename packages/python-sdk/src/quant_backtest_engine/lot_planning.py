"""Exact bounded native lot-planning protocol; execution remains separately owned."""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal, localcontext
from itertools import product


def require(condition, message):
    if not condition:
        raise ValueError(message)


def shape(value, keys):
    require(
        type(value) is dict and set(value) == set(keys.split()),
        "unexpected lot protocol fields",
    )


def amount(value, maximum=10**20, precision=8):
    require(
        type(value) is str
        and len(value) <= 40
        and re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value),
        "canonical decimal string required",
    )
    result = Decimal(value)
    require(
        result <= maximum and -result.as_tuple().exponent <= precision,
        "lot amount outside supported range",
    )
    return result


def integer(value, low=0, high=2**64 - 1):
    require(
        type(value) is int and low <= value <= high,
        "lot integer outside supported range",
    )
    return value


def validate_request(r):
    shape(
        r,
        "schema_version prices target_quantities max_lots lot_sizes cash_budget minimum_commission proportional_commission max_states candidate_quantities",
    )
    require(r["schema_version"] == "engine_lot_request.v1", "unsupported lot schema")
    require(
        all(
            type(r[k]) is list
            for k in ("prices", "target_quantities", "max_lots", "lot_sizes")
        ),
        "lot vectors must be arrays",
    )
    n = len(r["prices"])
    require(
        1 <= n <= 16
        and all(len(r[k]) == n for k in ("target_quantities", "max_lots", "lot_sizes")),
        "1..16 aligned assets required",
    )
    for value in r["prices"]:
        require(amount(value, 10**6, 4) > 0, "positive price required")
    for value in r["target_quantities"]:
        amount(value, 10**9, 4)
    for bound, lot in zip(r["max_lots"], r["lot_sizes"]):
        integer(bound)
        integer(lot, 1, 10**9)
        require(bound * lot <= 10**9, "quantity bound exceeded")
    amount(r["cash_budget"], 10**12, 4)
    amount(r["minimum_commission"], 10**6, 4)
    amount(r["proportional_commission"], 1, 4)
    integer(r["max_states"], 1, 100000)
    if r["candidate_quantities"] is not None:
        require(type(r["candidate_quantities"]) is list, "candidate must be an array")
        for value in r["candidate_quantities"]:
            integer(value)


def _evaluate(r, q):
    require(
        type(q) is list and len(q) == len(r["prices"]),
        "aligned quantity array required",
    )
    for v, b, l in zip(q, r["max_lots"], r["lot_sizes"]):
        integer(v)
        require(v <= b * l and v % l == 0, "quantity outside lot grid")
    prices = list(map(Decimal, r["prices"]))
    targets = list(map(Decimal, r["target_quantities"]))
    rate = Decimal(r["proportional_commission"])
    minimum = Decimal(r["minimum_commission"])
    spent = sum(
        (p * v + (max(minimum, rate * p * v) if v else 0) for p, v in zip(prices, q)),
        Decimal(0),
    )
    loss = sum(((Decimal(v) - t) ** 2 for v, t in zip(q, targets)), Decimal(0))
    require(spent <= Decimal(r["cash_budget"]), "quantity exceeds cash budget")
    return spent, loss


def _prove_optimum(r, quantities, objective):
    """Independent scaled-integer certificate check over the admitted finite grid.

    Four input decimal places yield exact scale-eight fees and squared errors.
    No currency rounding or second execution account is introduced.
    """
    scale = 10000
    prices = [int(Decimal(p) * scale) for p in r["prices"]]
    targets = [int(Decimal(t) * scale) for t in r["target_quantities"]]
    minimum = int(Decimal(r["minimum_commission"]) * scale * scale)
    rate = int(Decimal(r["proportional_commission"]) * scale)
    budget = int(Decimal(r["cash_budget"]) * scale * scale)
    domains = []
    for p, t, b, l in zip(prices, targets, r["max_lots"], r["lot_sizes"]):
        states = []
        for count in range(b + 1):
            q = count * l
            cost = p * q * scale + (max(minimum, rate * p * q) if q else 0)
            states.append((q, cost, (q * scale - t) ** 2))
        domains.append(states)
    best = None
    for state in product(*domains):
        if sum(v[1] for v in state) > budget:
            continue
        loss = sum(v[2] for v in state)
        if best is None or loss < best[0]:
            best = (loss, tuple(v[0] for v in state))
    require(
        best is not None
        and best == (int(objective * scale * scale), tuple(quantities)),
        "native optimum or lexicographic tie fails independent integer proof",
    )


def validate_result(request, result):
    validate_request(request)
    shape(
        result,
        "schema_version request_sha256 status quantities objective spent evaluated domain_states candidate_status candidate_gap",
    )
    digest = hashlib.sha256(
        json.dumps(
            request, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    require(
        result["schema_version"] == "engine_lot_result.v1"
        and result["request_sha256"] == digest,
        "lot result identity mismatch",
    )
    states = math.prod(v + 1 for v in request["max_lots"])
    reported = states if states <= 2**64 - 1 else None
    require(
        result["domain_states"] == reported
        and (reported is None or type(result["domain_states"]) is int),
        "lot domain mismatch",
    )
    integer(result["evaluated"])
    if states > request["max_states"]:
        require(
            result["status"] == "search_limit"
            and result["evaluated"] == 0
            and all(
                result[k] is None
                for k in ("quantities", "objective", "spent", "candidate_gap")
            )
            and result["candidate_status"] == "not_provided",
            "search limit produced a plan",
        )
        return result
    require(
        result["status"] == "optimal_exhaustive" and result["evaluated"] == states,
        "incomplete exhaustive result",
    )
    with localcontext() as ctx:
        ctx.prec = 80
        spent, loss = _evaluate(request, result["quantities"])
        require(
            amount(result["spent"]) == spent and amount(result["objective"]) == loss,
            "lot plan economics mismatch",
        )
        _prove_optimum(request, result["quantities"], loss)
        status = "not_provided"
        gap = None
        if request["candidate_quantities"] is not None:
            status = "infeasible"
            try:
                _, candidate_loss = _evaluate(request, request["candidate_quantities"])
            except ValueError:
                pass
            else:
                status = "feasible"
                gap = candidate_loss - loss
                require(gap >= 0, "candidate improves claimed optimum")
        require(result["candidate_status"] == status, "candidate feasibility mismatch")
        require(
            result["candidate_gap"] is None
            if gap is None
            else amount(result["candidate_gap"]) == gap,
            "candidate gap mismatch",
        )
    return result
