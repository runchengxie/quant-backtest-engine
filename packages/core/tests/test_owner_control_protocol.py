from quant_backtest_core.planning.owner_control_protocol import case_id, fixed_panels


def test_registered_panels_have104rows_and96distinct_cases():
    rows = fixed_panels()
    assert len(rows) == 104
    assert len({case_id(c) for _, c in rows}) == 96
    assert [sum(p == name for p, _ in rows) for name in ["impact", "capacity", "feedback"]] == [
        36,
        36,
        32,
    ]
    assert len({case_id(c) for p, c in rows if p == "impact"}) == 36
