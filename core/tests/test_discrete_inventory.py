# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_discrete_inventory.py
"""Literal finite-domain and owner-ledger checks, using synthetic inputs only."""

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from itertools import product

import pandas as pd
import pytest

from quant_backtest_core.planning.discrete_inventory import (
    DiscreteInventoryRequest,
    solve_discrete_inventory,
)


def request(**kwargs):
    base = {
        "prices": (6, 4),
        "holdings": (0, 0),
        "target_shares": ("1.5", "1.5"),
        "available_sell_shares": (0, 0),
        "buy_lot_sizes": (1, 1),
        "sell_lot_sizes": (1, 1),
        "max_buy_lots": (3, 3),
        "cash": 14,
        "minimum_fee": 1,
    }
    return DiscreteInventoryRequest(**(base | kwargs))


def test_literal_exhaustive_fixture_and_feasible_local_heuristic():
    # Independent complete feasible list: fees leave room for just these states.
    literal = {
        (0, 0): (Fraction(9, 2), 14),
        (0, 1): (Fraction(5, 2), 9),
        (0, 2): (Fraction(5, 2), 5),
        (0, 3): (Fraction(9, 2), 1),
        (1, 0): (Fraction(5, 2), 7),
        (1, 1): (Fraction(1, 2), 2),
        (2, 0): (Fraction(5, 2), 1),
    }
    result = solve_discrete_inventory(request())
    assert result.status == "optimal_exhaustive"
    assert result.domain_states == result.evaluated == 16
    assert result.incumbent.trades == min(literal, key=lambda q: (literal[q][0], q))
    assert (result.incumbent.objective, result.incumbent.projected_cash) == literal[(1, 1)]
    assert result.heuristic.trades == (1, 1)
    assert result.heuristic.objective == Fraction(1, 2)
    assert result.heuristic_gap == 0
    assert result.lower_bound == result.upper_bound == Fraction(1, 2)

    # An exact grid target is the unique zero-error plan when it is feasible.
    # Changing only the target preserves the original funding/fee domain.
    for state in product(range(4), repeat=2):
        targeted = solve_discrete_inventory(request(target_shares=state))
        assert targeted.status == "optimal_exhaustive"
        assert targeted.domain_states == targeted.evaluated == 16
        assert targeted.incumbent.trades in literal
        assert targeted.incumbent.projected_cash == literal[targeted.incumbent.trades][1]
        if state in literal:
            assert targeted.incumbent.trades == state
            assert targeted.incumbent.objective == 0
            assert targeted.incumbent.projected_cash == literal[state][1]
        else:
            assert targeted.incumbent.trades != state
            assert targeted.incumbent.objective > 0


def test_minimum_fixed_and_proportional_fees_change_feasible_winner():
    no_fee = solve_discrete_inventory(request(minimum_fee=0, target_shares=("1.6", "1.6")))
    assert no_fee.incumbent.trades == (1, 2)
    minimum = solve_discrete_inventory(request(target_shares=("1.6", "1.6")))
    assert minimum.incumbent.trades == (1, 1)
    combined = solve_discrete_inventory(
        request(
            prices=(10,),
            holdings=(0,),
            target_shares=(2,),
            available_sell_shares=(0,),
            buy_lot_sizes=(1,),
            sell_lot_sizes=(1,),
            max_buy_lots=(2,),
            cash="21.99",
            minimum_fee=1,
            fixed_fee=1,
            proportional_fee="0.1",
        )
    )
    assert combined.incumbent.trades == (1,)
    assert combined.incumbent.fees == 2


def test_projected_sale_is_not_buy_funding_and_replan_uses_actual_cash():
    base = request(
        prices=(10, 10),
        holdings=(10, 0),
        target_shares=(0, 10),
        available_sell_shares=(10, 0),
        max_buy_lots=(0, 10),
        cash=0,
        minimum_fee=0,
    )
    first = solve_discrete_inventory(base)
    assert first.incumbent.trades == (-10, 0)
    assert first.incumbent.projected_cash == 100
    assert first.incumbent.unreserved_cash == 0
    # Only the caller's later actual owner settlement may change holdings and cash.
    after = solve_discrete_inventory(
        replace(base, holdings=(0, 0), available_sell_shares=(0, 0), cash=100)
    )
    assert after.incumbent.trades == (0, 10)
    assert after.incumbent.projected_cash == 0


def test_zero_cash_sell_fee_is_explicitly_prefunded():
    result = solve_discrete_inventory(
        request(
            prices=(10,),
            holdings=(10,),
            target_shares=(0,),
            available_sell_shares=(10,),
            buy_lot_sizes=(1,),
            sell_lot_sizes=(1,),
            max_buy_lots=(0,),
            cash=0,
        )
    )
    assert result.incumbent.trades == (0,)
    assert result.funding_policy == "prefund_all_orders_no_sale_recycling"


def test_locked_t1_odd_lot_and_fractional_entitlement_are_preserved():
    base = request(
        prices=(1,),
        holdings=(250,),
        target_shares=(0,),
        available_sell_shares=(250,),
        locked_shares=(50,),
        buy_lot_sizes=(100,),
        sell_lot_sizes=(100,),
        max_buy_lots=(0,),
        fractional_entitlements=("0.5",),
        cash=5,
    )
    partial = solve_discrete_inventory(base).incumbent
    assert partial.trades == (-200,)
    assert partial.holdings == (50,)
    assert partial.fractional_entitlements == (Fraction(1, 2),)
    assert partial.objective == Fraction(10201, 4)
    t1 = solve_discrete_inventory(replace(base, available_sell_shares=(175,))).incumbent
    assert t1.trades == (-100,)
    complete = solve_discrete_inventory(replace(base, locked_shares=(0,))).incumbent
    assert complete.trades == (-250,)
    assert complete.holdings == (0,)
    assert complete.fractional_entitlements == (Fraction(1, 2),)
    ordinary = solve_discrete_inventory(
        replace(base, locked_shares=(0,), allow_odd_lot_exit=False)
    ).incumbent
    assert ordinary.trades == (-200,)


def test_exact_decimal_boundary_reservation_and_infeasible_rounding():
    base = request(
        prices=(Decimal("0.1"), "0.2"),
        target_shares=(1, 1),
        max_buy_lots=(1, 1),
        cash="0.4",
        reserved_cash="0.1",
        minimum_fee=0,
    )
    assert solve_discrete_inventory(base).incumbent.trades == (1, 1)
    under = solve_discrete_inventory(replace(base, cash="0.399999999999999999"))
    assert under.incumbent.trades == (0, 1)
    assert under.incumbent.projected_cash == Fraction("0.199999999999999999")
    rounded = solve_discrete_inventory(
        request(
            prices=(6,),
            holdings=(0,),
            target_shares=(2,),
            available_sell_shares=(0,),
            buy_lot_sizes=(2,),
            sell_lot_sizes=(1,),
            max_buy_lots=(1,),
            cash=12,
            minimum_fee=1,
        )
    )
    assert rounded.incumbent.trades == (0,)


def test_weighted_tracking_and_nonnegative_turnover_are_declared():
    result = solve_discrete_inventory(
        request(
            prices=(1,),
            holdings=(0,),
            target_shares=(2,),
            available_sell_shares=(0,),
            buy_lot_sizes=(1,),
            sell_lot_sizes=(1,),
            max_buy_lots=(3,),
            tracking_weights=(2,),
            turnover_penalties=(5,),
            cash=100,
            minimum_fee=0,
        )
    )
    assert result.incumbent.trades == (1,)
    assert result.incumbent.objective == 7


def test_caps_budget_exhaustion_and_ties_never_fabricate_optimality():
    base = request()
    exhausted = solve_discrete_inventory(replace(base, max_evaluations=1))
    assert exhausted.status == "budget_exhausted"
    assert exhausted.evaluated == 1
    assert exhausted.lower_bound == 0
    assert exhausted.upper_bound == exhausted.incumbent.objective
    assert exhausted.heuristic_gap is None
    large = solve_discrete_inventory(replace(base, max_domain_states=10))
    assert large.status == "domain_too_large"
    assert large.evaluated == 0 and large.heuristic is not None
    asset_cap = solve_discrete_inventory(replace(base, max_assets=1))
    assert asset_cap.status == "asset_limit" and asset_cap.incumbent is None
    domain_cap = solve_discrete_inventory(replace(base, max_asset_states=2))
    assert domain_cap.status == "asset_domain_limit" and domain_cap.incumbent is None
    heuristic_cap = solve_discrete_inventory(replace(base, max_heuristic_evaluations=1))
    assert heuristic_cap.heuristic_status == "budget_exhausted"
    tie = request(
        prices=(1,),
        holdings=(0,),
        target_shares=("0.5",),
        available_sell_shares=(0,),
        buy_lot_sizes=(1,),
        sell_lot_sizes=(1,),
        max_buy_lots=(1,),
        cash=10,
        minimum_fee=0,
    )
    assert solve_discrete_inventory(tie).incumbent.trades == (0,)
    assert solve_discrete_inventory(tie) == solve_discrete_inventory(tie)


@pytest.mark.parametrize(
    "change",
    [
        {"holdings": (0.5, 0)},
        {"available_sell_shares": (1, 0)},
        {"locked_shares": (1, 0)},
        {"prices": (True, 4)},
        {"prices": ("NaN", 4)},
        {"target_shares": (-1, 1)},
        {"fractional_entitlements": (1, 0)},
        {"tracking_weights": (-1, 1)},
        {"turnover_penalties": (-1, 0)},
        {"reserved_cash": 15},
        {"max_evaluations": True},
        {"max_buy_lots": (10**9, 1.5)},
        {"allow_odd_lot_exit": 1},
        {"buy_lot_sizes": (0, 1)},
        {"prices": (1,)},
    ],
)
def test_invalid_contract_fails_closed(change):
    with pytest.raises(ValueError):
        solve_discrete_inventory(request(**change))


@pytest.mark.parametrize("selection", ["heuristic", "incumbent"])
def test_both_plans_use_public_owner_fills_fees_cash_and_residual_tracking(selection):
    result = solve_discrete_inventory(request(prices=(4, 6), target_shares=("1.9", "1.9")))
    assert result.heuristic_gap == 2
    plan = getattr(result, selection)
    symbols = ("AAA", "BBB")
    # Task 14/15 parity obligation: original dated-fee daily-owner variant.
    # This fixture uses the reviewed minute owner; literal economics below are unchanged.
    delivered = minute_result(
        (("2026-01-05", tuple(q * p / 14 for q, p in zip(plan.holdings, (4, 6), strict=True))),),
        prices=(4, 6),
        cash=14,
        minimum=1,
    )
    literal = {
        "heuristic": ([8.0], [1.0], 5.0, 8.0, Fraction(181, 50)),
        "incumbent": ([4.0, 6.0], [1.0, 1.0], 2.0, 10.0, Fraction(81, 50)),
    }
    notionals, fees, cash, invested, residual = literal[selection]
    assert delivered.fills["gross_amount"].tolist() == notionals
    assert delivered.fills["transaction_cost"].tolist() == fees
    assert delivered.daily.iloc[-1]["cash"] == pytest.approx(cash)
    assert delivered.daily.iloc[-1]["positions_value"] == pytest.approx(invested)
    actual_shares = dict(
        zip(
            delivered.fills["symbol"],
            delivered.fills["gross_amount"]
            / delivered.fills["symbol"].map(dict(zip(symbols, (4, 6), strict=False))),
            strict=True,
        )
    )
    actual_error = sum((actual_shares.get(s, 0) - 1.9) ** 2 for s in symbols)
    assert actual_error == pytest.approx(float(residual))
    assert residual == plan.objective
    assert sum(notionals) == float(plan.turnover_notional)
    assert sum(fees) == float(plan.fees)
    assert cash == float(plan.projected_cash)


@pytest.mark.parametrize("sale_fills", [False, True])
def test_actual_public_owner_sale_controls_later_buy_funding(sale_fills):
    base = request(
        prices=(10, 10),
        holdings=(10, 0),
        target_shares=(0, 10),
        available_sell_shares=(10, 0),
        max_buy_lots=(0, 10),
        cash=0,
        minimum_fee=0,
    )
    planned = solve_discrete_inventory(base).incumbent
    assert planned.trades == (-10, 0)
    # Task 14/15 parity obligation: original daily-owner sale-funding variant.
    # Seed a genuine prior-day purchase and restore the whole owner before exit.
    delivered = minute_result(
        (("2026-01-05", (1, 0)), ("2026-01-06", tuple(q / 10 for q in planned.holdings))),
        prices=(10, 10),
        cash=100,
        sale_fills=sale_fills,
        restore_before_exit=True,
    )
    sells = delivered.fills.loc[delivered.fills["side"].eq("sell")]
    assert sells["gross_amount"].tolist() == ([100.0] if sale_fills else [])
    actual_cash = delivered.daily.iloc[-1]["cash"]
    assert actual_cash == (100 if sale_fills else 0)
    assert delivered.daily.iloc[-1]["positions_value"] == (0 if sale_fills else 100)
    actual_holdings = (0, 0) if sale_fills else (10, 0)
    replanned = solve_discrete_inventory(
        replace(
            base,
            cash=actual_cash,
            holdings=actual_holdings,
            available_sell_shares=(0, 0),
        )
    )
    assert replanned.incumbent.trades == ((0, 10) if sale_fills else (0, 0))


def minute_result(days, *, prices, cash, minimum=0, sale_fills=True, restore_before_exit=False):
    """Synthetic minute fixture; no shadow ledger or manufactured financial result."""
    from test_minute_execution import bars
    from test_minute_session import Policy

    from quant_backtest_core.backtest.minute import MinuteExecutionConfig
    from quant_backtest_core.backtest.minute_session import MinuteSession

    symbols = ("AAA", "BBB")
    targets = pd.DataFrame(
        [
            {
                "decision_time": pd.Timestamp(day + " 09:29", tz="Asia/Shanghai"),
                "entry_time": pd.Timestamp(day + " 09:30", tz="Asia/Shanghai"),
                "symbol": symbol,
                "weight": weight,
            }
            for day, weights in days
            for symbol, weight in zip(symbols, weights, strict=True)
        ]
    )
    frames = []
    for index, (day, _) in enumerate(days):
        for symbol, price in zip(symbols, prices, strict=True):
            frame = bars(
                (day + " 09:29", day + " 09:32"),
                price=price,
                volume=1000 if index == 0 or sale_fills else 0,
            )
            frame["symbol"] = symbol
            frame["up_limit"], frame["down_limit"] = price * 1.1, price * 0.9
            frames.append(frame)
    market = pd.concat(frames, ignore_index=True)
    config = MinuteExecutionConfig(cash, 1, 0, 0, lot_size=1, commission_minimum_cny=minimum)
    session = MinuteSession(targets, market, config, policy=Policy())
    if restore_before_exit:
        while session.simulation.times[session.cursor].date().isoformat() == days[0][0]:
            assert session.step()
        assert session.delivered["cash"] == 0
        assert session.delivered["holdings"] == {"AAA": 10}
        state = session.checkpoint()
        policy = Policy()
        policy.rows = state["policy"]
        restored = MinuteSession.restore(targets, market, config, state, policy=policy)
        assert restored.checkpoint() == state
        expected, actual = session.run(), restored.run()
        for table in ("daily", "fills", "orders", "holdings"):
            pd.testing.assert_frame_equal(getattr(expected, table), getattr(actual, table))
        assert expected.summary == actual.summary
        return actual
    return session.run()
