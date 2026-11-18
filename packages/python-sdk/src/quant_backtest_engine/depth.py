"""Strict standard-library codecs for the opt-in native L2 event boundary."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, localcontext

CAPABILITIES = (
    "l2_depth_events",
    "trade_events",
    "limit_orders",
    "cancel_orders",
    "command_latency",
    "account_feedback_targets",
    "final_balances",
    "proportional_fees",
)
MAX_NS = 4_102_444_800_000_000_000


def shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError("unexpected depth object fields")


def integer(value, minimum=0, maximum=MAX_NS):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("integer outside depth contract range")
    return value


def number(value, precision=4, maximum=1_000_000_000_000_000_000, positive=False):
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value
    ):
        raise ValueError("canonical nonnegative decimal string required")
    n = Decimal(value)
    if -n.as_tuple().exponent > precision or n > maximum or (positive and not n):
        raise ValueError("depth decimal outside range/precision")
    return n


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value):
        raise ValueError("invalid depth identity")


def validate_request(r):
    shape(
        r,
        "schema_version currency initial_cash fee_bps instrument insert_latency_ns cancel_latency_ns end_ns events commands required_capabilities",
    )
    if r["schema_version"] != "engine_depth_request.v1" or r["currency"] not in (
        "CNY",
        "USD",
    ):
        raise ValueError("unsupported depth schema/currency")
    number(r["initial_cash"], 2, 1_000_000_000_000, positive=True)
    number(r["fee_bps"], 4, 1000)
    shape(r["instrument"], "symbol price_precision")
    identifier(r["instrument"]["symbol"])
    precision = integer(r["instrument"]["price_precision"], 0, 4)
    integer(r["insert_latency_ns"], 0, 60_000_000_000)
    integer(r["cancel_latency_ns"], 0, 60_000_000_000)
    end = integer(r["end_ns"], 1)
    if type(r["events"]) is not list or not 1 <= len(r["events"]) <= 100_000:
        raise ValueError("invalid event budget")
    if type(r["commands"]) is not list or len(r["commands"]) > 10_000:
        raise ValueError("invalid command budget")
    levels = {"bids": {}, "asks": {}}
    keys = {}
    previous_time = 0
    previous_seq = 0
    trade_ids = set()
    last_depth = 0
    depth_rows = 0
    for i, e in enumerate(r["events"]):
        shape(
            e,
            "kind ts_ns available_ns sequence bids asks trade_id trade_price trade_quantity aggressor",
        )
        ts = integer(e["ts_ns"], 1)
        available = integer(e["available_ns"], 1)
        seq = integer(e["sequence"], 1, 2**64 - 1)
        if (
            ts != available
            or available < previous_time
            or available > end
            or seq <= previous_seq
        ):
            raise ValueError("invalid event order or availability")
        if i == 0 and e["kind"] != "snapshot":
            raise ValueError("initial snapshot required")
        keys[seq] = available
        previous_time = available
        previous_seq = seq
        if any(type(e[k]) is not list or len(e[k]) > 100 for k in ("bids", "asks")):
            raise ValueError("invalid depth level budget")
        depth_rows += len(e["bids"]) + len(e["asks"])
        if depth_rows > 1_000_000:
            raise ValueError("depth row budget exceeded")
        if e["kind"] == "trade":
            identifier(e["trade_id"])
            if e["trade_id"] in trade_ids:
                raise ValueError("duplicate market trade identity")
            trade_ids.add(e["trade_id"])
            if e["bids"] or e["asks"] or e["aggressor"] not in ("buy", "sell"):
                raise ValueError("invalid trade semantics")
            number(e["trade_price"], precision, 1_000_000, True)
            number(e["trade_quantity"], 0, 1_000_000_000, True)
        elif e["kind"] in ("snapshot", "delta"):
            last_depth = available
            if any(
                e[k] is not None
                for k in ("trade_id", "trade_price", "trade_quantity", "aggressor")
            ) or not (e["bids"] or e["asks"]):
                raise ValueError("invalid depth semantics")
            if e["kind"] == "snapshot":
                levels = {"bids": {}, "asks": {}}
            for side in ("bids", "asks"):
                seen = set()
                for level in e[side]:
                    shape(level, "price quantity")
                    price = number(level["price"], precision, 1_000_000, True)
                    qty = number(level["quantity"], 0, 1_000_000_000)
                    if price in seen:
                        raise ValueError("duplicate depth price")
                    seen.add(price)
                    if qty:
                        levels[side][price] = qty
                    elif e["kind"] == "delta" and price in levels[side]:
                        del levels[side][price]
                    else:
                        raise ValueError("invalid depth deletion")
            if not all(levels.values()) or max(levels["bids"]) >= min(levels["asks"]):
                raise ValueError("empty, crossed or locked book")
        else:
            raise ValueError("unsupported event kind")
    if end - last_depth > 60_000_000_000:
        raise ValueError("final depth valuation is stale")
    ids = set()
    orders = set()
    previous_seq = -1
    buy_budget = Decimal(0)
    for c in r["commands"]:
        shape(
            c,
            "id event_sequence information_ts_ns action quantity limit_price cancel_id",
        )
        identifier(c["id"])
        if c["id"] in ids:
            raise ValueError("duplicate command identity")
        ids.add(c["id"])
        seq = integer(c["event_sequence"], 1, 2**64 - 1)
        if seq not in keys or seq <= previous_seq:
            raise ValueError("invalid command order")
        previous_seq = seq
        if integer(c["information_ts_ns"], 1) >= keys[seq]:
            raise ValueError("future command information")
        latency = (
            r["cancel_latency_ns"]
            if c["action"] == "cancel"
            else r["insert_latency_ns"]
        )
        if keys[seq] + latency >= end:
            raise ValueError("horizon ends before command observation")
        qty = number(c["quantity"], 0, 1_000_000_000)
        if c["action"] in ("buy", "sell", "target"):
            if c["action"] != "sell":
                buy_budget += qty
            if buy_budget > 1_000_000_000:
                raise ValueError("aggregate buy/target quantity budget exceeded")
            if c["cancel_id"] is not None or (c["action"] != "target" and not qty):
                raise ValueError("invalid order command")
            number(c["limit_price"], precision, 1_000_000, True)
            orders.add(c["id"])
        elif c["action"] == "cancel":
            if qty or c["limit_price"] != "0" or c["cancel_id"] not in orders:
                raise ValueError("invalid cancellation")
        else:
            raise ValueError("unsupported command action")
    caps = r["required_capabilities"]
    if (
        type(caps) is not list
        or any(type(c) is not str or c not in CAPABILITIES for c in caps)
        or len(set(caps)) != len(caps)
    ):
        raise ValueError("invalid depth capabilities")


def validate_result(request, result):
    """Reconcile native evidence and observed account prefixes; never execute orders."""
    from collections import Counter
    from decimal import ROUND_HALF_EVEN

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def money(value):
        return number(value, 2)

    def rounded(value):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

    def fill_key(fill):
        return tuple(
            fill[k]
            for k in (
                "order_id",
                "symbol",
                "side",
                "ts_ns",
                "quantity",
                "price",
                "commission",
            )
        )

    shape(
        result,
        "schema_version request_sha256 capabilities decisions receipts fill_order valuation_ns observation_ns account",
    )
    require(
        result["schema_version"] == "engine_depth_result.v1"
        and result["capabilities"] == list(CAPABILITIES),
        "unexpected depth capabilities",
    )
    digest = hashlib.sha256(
        json.dumps(
            request, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    require(result["request_sha256"] == digest, "depth request digest mismatch")
    start = request["events"][0]["available_ns"]
    end = request["end_ns"]
    keys = {e["sequence"]: e["available_ns"] for e in request["events"]}
    commands = {c["id"]: c for c in request["commands"]}
    symbol = request["instrument"]["symbol"]
    precision = request["instrument"]["price_precision"]
    last_depth = next(e for e in reversed(request["events"]) if e["kind"] != "trade")
    require(
        type(result["valuation_ns"]) is int
        and result["valuation_ns"] == last_depth["available_ns"]
        and type(result["observation_ns"]) is int
        and result["observation_ns"] == end,
        "valuation/observation clock mismatch",
    )
    book = {"bids": {}, "asks": {}}
    for event in request["events"]:
        if event["kind"] == "trade":
            continue
        if event["kind"] == "snapshot":
            book = {"bids": {}, "asks": {}}
        for side in book:
            for level in event[side]:
                price = Decimal(level["price"])
                qty = Decimal(level["quantity"])
                if qty:
                    book[side][price] = qty
                else:
                    del book[side][price]
    with localcontext() as context:
        context.prec = 64
        mark = (max(book["bids"]) + min(book["asks"])) / 2
        account = result["account"]
        shape(
            account,
            "schema_version backend backend_version capabilities currency cash positions_value equity commission orders fills positions",
        )
        require(
            (
                account["schema_version"],
                account["backend"],
                account["backend_version"],
                account["currency"],
            )
            == ("engine_depth_account.v1", "nautilus", "0.66.0", request["currency"])
            and account["capabilities"] == list(CAPABILITIES),
            "depth account identity mismatch",
        )
        require(
            all(type(account[k]) is list for k in ("orders", "fills", "positions"))
            and all(
                type(result[k]) is list for k in ("decisions", "receipts", "fill_order")
            ),
            "depth evidence must use arrays",
        )
        require(len(result["decisions"]) == len(commands), "decision coverage mismatch")
        receipts = {}
        executions = {}
        previous_received = start
        for receipt in result["receipts"]:
            shape(receipt, "order_id kind ts_ns received_ns trade_id fill")
            oid = receipt["order_id"]
            kind = receipt["kind"]
            require(
                oid in commands and commands[oid]["action"] != "cancel",
                "unexpected receipt order identity",
            )
            ts = integer(receipt["ts_ns"], 1)
            received = integer(receipt["received_ns"], 1)
            require(
                start <= ts <= received <= end and received >= previous_received,
                "receipt clock outside run or delivery order",
            )
            previous_received = received
            require(
                kind
                in (
                    "filled",
                    "accepted",
                    "canceled",
                    "cancel_rejected",
                    "rejected",
                    "denied",
                ),
                "unsupported order receipt",
            )
            command = commands[oid]
            minimum = keys[command["event_sequence"]] + (
                0
                if kind in ("denied", "canceled", "cancel_rejected")
                else request["insert_latency_ns"]
            )
            require(ts >= minimum, "receipt precedes order eligibility")
            if kind in ("canceled", "cancel_rejected"):
                require(
                    any(
                        c["action"] == "cancel"
                        and c["cancel_id"] == oid
                        and ts
                        >= keys[c["event_sequence"]] + request["cancel_latency_ns"]
                        for c in request["commands"]
                    ),
                    "cancellation receipt has no eligible command",
                )
            receipts.setdefault(oid, []).append(receipt)
            if kind == "filled":
                trade = receipt["trade_id"]
                fill = receipt["fill"]
                require(
                    isinstance(trade, str) and trade and trade not in executions,
                    "unique native trade identity required",
                )
                shape(fill, "order_id symbol side ts_ns quantity price commission")
                require(
                    fill["order_id"] == oid and fill["ts_ns"] == ts,
                    "fill receipt identity/clock mismatch",
                )
                executions[trade] = fill
            else:
                require(
                    receipt["trade_id"] is None and receipt["fill"] is None,
                    "unexpected financial payload in non-fill receipt",
                )
        for fill in account["fills"]:
            shape(fill, "order_id symbol side ts_ns quantity price commission")
        require(
            Counter(fill_key(f) for f in account["fills"])
            == Counter(fill_key(f) for f in executions.values()),
            "account fills differ from native receipts",
        )
        order = result["fill_order"]
        require(
            all(isinstance(k, str) for k in order)
            and len(order) == len(set(order))
            and set(order) == set(executions),
            "native fill observation order is incomplete or duplicated",
        )
        # Build immutable prefixes once, using native Money rounding for each fill.
        cash_prefix = [money(request["initial_cash"])]
        quantity_prefix = [Decimal(0)]
        fee_total = Decimal(0)
        fill_times = []
        for trade in order:
            fill = executions[trade]
            require(
                fill["order_id"] in commands
                and fill["symbol"] == symbol
                and fill["side"] in ("buy", "sell"),
                "invalid native fill identity",
            )
            ts = integer(fill["ts_ns"], 1)
            fill_times.append(ts)
            if len(fill_times) > 1:
                require(ts >= fill_times[-2], "native fill observations reverse time")
            qty = number(fill["quantity"], 0, positive=True)
            price = number(fill["price"], precision, positive=True)
            fee = money(fill["commission"])
            notional = rounded(qty * price)
            require(
                fee == rounded(notional * Decimal(request["fee_bps"]) / 10000),
                "fee differs from configured native model",
            )
            sign = 1 if fill["side"] == "buy" else -1
            quantity_prefix.append(quantity_prefix[-1] + sign * qty)
            require(quantity_prefix[-1] >= 0, "short position is unsupported")
            cash_prefix.append(cash_prefix[-1] - sign * notional - fee)
            fee_total += fee
        generated = {}
        previous_count = 0
        observed_quantities = {}
        for decision, command in zip(result["decisions"], request["commands"]):
            shape(
                decision,
                "id ts_ns action held_quantity free_cash admissible_cash total_cash locked_cash observed_fill_count working_order_ids submitted_quantity outcome",
            )
            now = keys[command["event_sequence"]]
            require(
                decision["id"] == command["id"]
                and decision["action"] == command["action"]
                and type(decision["ts_ns"]) is int
                and decision["ts_ns"] == now,
                "decision identity/clock mismatch",
            )
            count = integer(decision["observed_fill_count"], 0, len(order))
            require(count >= previous_count, "decision fill observations reverse")
            for trade in order[previous_count:count]:
                fill = executions[trade]
                require(
                    fill["order_id"] in generated and fill["ts_ns"] <= now,
                    "decision observes a future or unsent fill",
                )
                oid = fill["order_id"]
                observed_quantities[oid] = observed_quantities.get(
                    oid, Decimal(0)
                ) + Decimal(fill["quantity"])
            previous_count = count
            require(
                count == len(order) or executions[order[count]]["ts_ns"] >= now,
                "decision omits an earlier fill",
            )
            held = number(decision["held_quantity"], 0)
            free = money(decision["free_cash"])
            total = money(decision["total_cash"])
            locked = money(decision["locked_cash"])
            require(
                held == quantity_prefix[count]
                and total == cash_prefix[count]
                and free + locked == total,
                "decision account differs from observed native fill prefix",
            )
            working = decision["working_order_ids"]
            require(
                type(working) is list
                and all(type(k) is str and k in generated for k in working)
                and len(set(working)) == len(working),
                "invalid working-order observation",
            )
            remaining = {
                oid: generated[oid][1] - observed_quantities.get(oid, Decimal(0))
                for oid in generated
            }
            for oid, details in generated.items():
                terminal = [
                    r
                    for r in receipts.get(oid, [])
                    if r["kind"] in ("denied", "rejected", "canceled")
                ]
                if (
                    details[3] != "submitted"
                    or not remaining[oid]
                    or any(r["received_ns"] < now for r in terminal)
                ):
                    require(oid not in working, "closed order reported as working")
                elif not any(r["received_ns"] <= now for r in terminal):
                    require(
                        oid in working, "unresolved order omitted from working state"
                    )
            require(
                all(remaining[k] > 0 for k in working),
                "fully filled order reported as working",
            )
            upper = sum(
                (
                    rounded(remaining[k] * generated[k][2])
                    + rounded(
                        rounded(remaining[k] * generated[k][2])
                        * Decimal(request["fee_bps"])
                        / 10000
                    )
                    for k in working
                ),
                Decimal(0),
            )
            require(locked <= upper, "locked cash exceeds working-order bound")
            buy_reserved = sum(
                (
                    rounded(remaining[k] * generated[k][2])
                    + rounded(
                        rounded(remaining[k] * generated[k][2])
                        * Decimal(request["fee_bps"])
                        / 10000
                    )
                    for k in working
                    if generated[k][0] == "buy"
                ),
                Decimal(0),
            )
            admissible = min(free, max(Decimal(0), total - buy_reserved))
            require(
                money(decision["admissible_cash"]) == admissible,
                "admission cash differs from native working-order envelope",
            )
            outcome = decision["outcome"]
            submitted = number(decision["submitted_quantity"], 0)
            if command["action"] == "cancel":
                require(
                    outcome
                    == (
                        "cancel_requested"
                        if command["cancel_id"] in working
                        else "not_working"
                    )
                    and not submitted,
                    "cancellation decision contradicts working orders",
                )
                continue
            signed = (
                Decimal(command["quantity"]) - held
                if command["action"] == "target"
                else Decimal(command["quantity"])
                * (1 if command["action"] == "buy" else -1)
            )
            if command["action"] == "target" and working:
                require(
                    outcome == "waiting_for_working_order" and not submitted,
                    "target ignores a working order",
                )
                continue
            if not signed:
                require(
                    outcome == "target_already_held" and not submitted,
                    "zero target generates an order",
                )
                continue
            side = "buy" if signed > 0 else "sell"
            qty = abs(signed)
            limit = Decimal(command["limit_price"])
            cost = rounded(qty * limit)
            cost += rounded(cost * Decimal(request["fee_bps"]) / 10000)
            sell_reserved = sum(
                (remaining[k] for k in working if generated[k][0] == "sell"), Decimal(0)
            )
            expected = (
                "denied_cash"
                if side == "buy" and cost > admissible
                else "denied_shares"
                if side == "sell" and qty > held - sell_reserved
                else "submitted"
            )
            require(
                outcome == expected
                and submitted == (qty if expected == "submitted" else 0),
                "submitted quantity or admission contradicts account evidence",
            )
            generated[command["id"]] = (side, qty, limit, expected)
        order_map = {}
        for item in account["orders"]:
            shape(item, "id symbol status filled_quantity")
            oid = item["id"]
            require(
                oid in generated and oid not in order_map and item["symbol"] == symbol,
                "unexpected native order identity",
            )
            order_map[oid] = item
        require(set(order_map) == set(generated), "missing generated order result")
        filled = {oid: Decimal(0) for oid in generated}
        for fill in executions.values():
            oid = fill["order_id"]
            require(oid in generated, "fill has no generated order")
            side, qty, limit, _ = generated[oid]
            actual = Decimal(fill["quantity"])
            price = Decimal(fill["price"])
            require(
                fill["side"] == side
                and (price <= limit if side == "buy" else price >= limit),
                "fill violates side or limit price",
            )
            filled[oid] += actual
        for oid, item in order_map.items():
            _, qty, _, admission = generated[oid]
            actual = number(item["filled_quantity"], 0)
            require(
                actual == filled[oid] and actual <= qty,
                "order overfill or inconsistent fills",
            )
            status = item["status"]
            kinds = {r["kind"] for r in receipts.get(oid, [])}
            if admission != "submitted":
                require(
                    status == "DENIED" and actual == 0 and "denied" in kinds,
                    "denied order has execution evidence",
                )
            elif status == "FILLED":
                require(
                    actual == qty and actual > 0 and "filled" in kinds,
                    "filled terminal status contradicts executions",
                )
            elif status == "PARTIALLY_FILLED":
                require(
                    0 < actual < qty and "filled" in kinds,
                    "partial status contradicts executions",
                )
            elif status == "ACCEPTED":
                require(
                    actual == 0 and "accepted" in kinds,
                    "accepted status contradicts executions",
                )
            elif status == "CANCELED":
                require(
                    actual < qty and "canceled" in kinds,
                    "cancel status lacks matching receipt",
                )
            elif status in ("DENIED", "REJECTED"):
                require(
                    actual == 0 and status.lower() in kinds,
                    "terminal rejection contradicts executions",
                )
            else:
                raise ValueError("unsupported terminal native order state")
        require(
            money(account["cash"]) == cash_prefix[-1]
            and money(account["commission"]) == fee_total,
            "native cash/fee evidence mismatch",
        )
        quantity = quantity_prefix[-1]
        require(
            len(account["positions"]) == (1 if quantity else 0),
            "position coverage mismatch",
        )
        value = Decimal(0)
        for position in account["positions"]:
            shape(position, "symbol quantity mark_price market_value")
            require(
                position["symbol"] == symbol
                and number(position["quantity"], 0) == quantity,
                "position quantity mismatch",
            )
            require(
                number(position["mark_price"], precision + 1) == mark,
                "mark differs from final supplied depth",
            )
            value = quantity * mark
            require(
                number(position["market_value"], precision + 1) == value,
                "position valuation mismatch",
            )
        require(
            number(account["positions_value"], precision + 1) == value
            and number(account["equity"], precision + 1) == cash_prefix[-1] + value,
            "native equity evidence mismatch",
        )
    return result
