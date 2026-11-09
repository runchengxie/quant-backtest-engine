import pandas as pd
import pytest

from quant_backtest_core.backtest.paper_account import (
    HouseMargin,
    Observed,
    PaperFill,
    PaperState,
    project_paper_account,
)

T = pd.Timestamp("2026-01-01", tz="UTC")


def run(
    state=None,
    days=0,
    price=10,
    fills=(),
    cap=100,
    rate=0.365,
    financing=0.365,
    dividends=None,
    **overrides,
):
    state = state or PaperState(T, 1000, {}, {})
    end = state.as_of + pd.Timedelta(days=days)
    args = {
        "as_of": end,
        "marks": {"X": Observed(price, end)},
        "borrow_rates": {"X": Observed(rate, state.as_of)},
        "locate_quantities": {"X": Observed(cap, end)},
        "financing_rate": Observed(financing, state.as_of),
        "financing_basis": "cash",
        "margin": HouseMargin(0.5, 1.5, 1),
        "max_age": pd.Timedelta(days=10),
        "fills": fills,
        "dividends": dividends or {},
    }
    args.update(overrides)
    return project_paper_account(state, **args)


def test_signed_cash_and_adverse_short_mark_with_partial_cover():
    opened = run(fills=[PaperFill("X", -10, 10, T, 1)])
    assert opened.state.cash == 1099
    assert opened.nav == 999
    assert opened.restricted_proceeds == 100
    end = T + pd.Timedelta(days=2)
    covered = run(
        opened.state, days=2, price=12, fills=[PaperFill("X", 4, 12, end, 1)], dividends={"X": 0.5}
    )
    assert covered.fill_fees == 1
    assert covered.borrow_cost == pytest.approx(0.2)
    assert covered.dividend_cash == -5  # pre-fill entitlement
    assert covered.state.cash == pytest.approx(1044.8)
    assert covered.state.quantities == {"X": -6}
    assert covered.nav == pytest.approx(972.8)
    assert covered.weights["X"] == pytest.approx(-72 / 972.8)
    assert covered.paper_only and not covered.executable


def test_financing_negative_cash_margin_and_insolvency():
    state = PaperState(T, -100, {"X": 20}, {"X": 10})
    result = run(state, days=2, price=1)
    assert result.financing_cost == pytest.approx(0.2)
    assert result.nav == pytest.approx(-80.2)
    assert result.insolvent and result.weights is None
    assert result.gross_leverage is None and result.net_leverage is None
    assert result.margin_breach
    assert result.state.quantities == {"X": 20}


def test_recall_allows_cover_but_rejects_increase():
    state = run(fills=[PaperFill("X", -10, 10, T)]).state
    result = run(state, cap=0, fills=[PaperFill("X", 3, 10, T)])
    assert result.borrow_breaches == ("X",)
    assert result.state.quantities == {"X": -7}
    with pytest.raises(ValueError, match="locate"):
        run(state, cap=5, fills=[PaperFill("X", -1, 10, T)])


@pytest.mark.parametrize(
    "overrides",
    [
        {"marks": {}},
        {"marks": {"X": Observed(float("nan"), T)}},
        {"marks": {"X": Observed(10, T + pd.Timedelta(seconds=1))}},
        {"marks": {"X": Observed(10, T - pd.Timedelta(days=11))}},
        {"borrow_rates": {}},
        {"locate_quantities": {}},
        {"as_of": pd.Timestamp("2026-01-01")},
        {"fills": [PaperFill("X", -1, 10, T + pd.Timedelta(seconds=1))]},
    ],
)
def test_invalid_or_incomplete_short_inputs_rejected(overrides):
    with pytest.raises(ValueError):
        run(**({"fills": [PaperFill("X", -1, 10, T)]} | overrides))


def test_future_accrual_rate_and_missing_prior_marks_rejected():
    state = PaperState(T, 1100, {"X": -10}, {"X": 10})
    with pytest.raises(ValueError):
        run(state, days=1, borrow_rates={"X": Observed(0.1, T + pd.Timedelta(hours=1))})
    with pytest.raises(ValueError):
        run(PaperState(T, 1100, {"X": -10}, {}), days=1)


def test_flat_ignores_zero_inventory_and_preserves_inputs():
    quantities = {"X": 0}
    state = PaperState(T, 100, quantities, {})
    quantities["X"] = 10
    result = run(state, marks={}, borrow_rates={}, locate_quantities={})
    assert result.nav == 100 and result.weights == {}
    assert result.gross_leverage == 0 and result.net_leverage == 0


@pytest.mark.parametrize(
    "fill",
    [
        PaperFill("X", -1, 10, T, -1),
        PaperFill("X", float("nan"), 10, T),
        PaperFill("X", -1, 0, T),
        PaperFill("", -1, 10, T),
        PaperFill("X", -1, 10, pd.Timestamp("2026-01-01")),
    ],
)
def test_invalid_fill_does_not_mutate_prior_state(fill):
    state = PaperState(T, 1000, {}, {})
    with pytest.raises(ValueError):
        run(state, fills=[fill])
    assert state.cash == 1000 and state.quantities == {}


def test_margin_breach_reports_without_liquidation_and_return_feedback():
    opened = run(fills=[PaperFill("X", -60, 10, T)])
    assert opened.margin_required == 900 and opened.margin_excess == 100
    adverse = run(opened.state, price=20)
    assert adverse.nav == 400 and adverse.margin_required == 1800
    assert adverse.margin_excess == -1400 and adverse.margin_breach
    assert adverse.state.quantities == {"X": -60}
    assert adverse.gross_leverage == 3 and adverse.net_leverage == -3
    assert adverse.weights == {"X": -3}


def test_fractional_calendar_days_and_long_dividends():
    state = PaperState(T, 0, {"X": 10}, {"X": 10})
    result = run(state, days=0.5, dividends={"X": 1.2})
    assert result.dividend_cash == 12 and result.nav == 112
    short = PaperState(T, 1100, {"X": -10}, {"X": 10})
    charged = run(short, days=0.5)
    assert charged.elapsed_days == 0.5 and charged.borrow_cost == pytest.approx(0.05)


def test_restricted_short_proceeds_can_require_funding_with_positive_cash():
    state = PaperState(T, 100, {"L": 35, "X": -35}, {"L": 10, "X": 10})
    result = run(
        state,
        days=2,
        financing_basis="unrestricted_cash",
        marks={
            "L": Observed(10, T + pd.Timedelta(days=2)),
            "X": Observed(10, T + pd.Timedelta(days=2)),
        },
    )
    assert result.financing_basis == "unrestricted_cash"
    assert result.financing_principal == 250
    assert result.financing_cost == pytest.approx(0.5)
    assert result.borrow_cost == pytest.approx(0.7)
    assert result.nav == pytest.approx(98.8)
    assert result.restricted_proceeds == 350
    cash_basis = run(
        state,
        days=2,
        financing_basis="cash",
        marks={
            "L": Observed(10, T + pd.Timedelta(days=2)),
            "X": Observed(10, T + pd.Timedelta(days=2)),
        },
    )
    assert cash_basis.financing_principal == 0 and cash_basis.financing_cost == 0
    with pytest.raises(ValueError):
        run(financing_basis="broker_actual")


def test_rejects_overflowing_restricted_proceeds():
    with pytest.raises(ValueError, match="finite"):
        run(fills=[PaperFill("X", -10, 10, T)], margin=HouseMargin(0, 0, 1e308))


def test_rejects_overflowing_gross_exposure_even_when_nav_finite():
    state = PaperState(T, 1e307, {"L": 9e307, "X": -9e307}, {"L": 1, "X": 1})
    with pytest.raises(ValueError, match="finite"):
        run(
            state,
            marks={"L": Observed(1, T), "X": Observed(1, T)},
            cap=1e308,
            rate=0,
            financing=0,
            margin=HouseMargin(0, 0, 0),
        )


def test_rejects_overflowing_weights_even_when_nav_positive():
    state = PaperState(T, 1e-308, {"L": 10, "X": -10}, {"L": 1, "X": 1})
    with pytest.raises(ValueError, match="finite"):
        run(
            state,
            marks={"L": Observed(1, T), "X": Observed(1, T)},
            cap=1e308,
            rate=0,
            financing=0,
            margin=HouseMargin(0, 0, 0),
        )


def test_rejects_overflowing_margin_excess_for_insolvent_account():
    state = PaperState(T, 0, {"X": -1}, {"X": 1e308})
    with pytest.raises(ValueError, match="finite"):
        run(state, price=1e308, rate=0, financing=0, margin=HouseMargin(0, 1, 0))
