"""Matched-horizon descriptive risk evidence, exported from the public owner."""


def build_risk_cases(records, scenario, number):
    from method_owner_calls import define_call, execute_call
    import pandas as pd

    forecasts, outcomes = [], []
    for index, (variance, realized) in enumerate(
        zip([1.0, 1.0, 4.0, 4.0], [1.0, -3.0, 2.0, -6.0], strict=True)
    ):
        start = pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=index)
        common = {
            "symbol": "A",
            "target_start": start,
            "target_end": start + pd.Timedelta(days=1),
            "unit": "return_bps",
        }
        forecasts.append(
            common
            | {
                "forecast_at": start,
                "available_at": start,
                "forecast_mean": 0.0,
                "forecast_variance": variance,
                "liquidity": "liquid" if index < 2 else "illiquid",
                "regime": "low" if index < 2 else "high",
            }
        )
        outcomes.append(
            common
            | {
                "realized": realized,
                "available_at": common["target_end"],
                "observation_start": start,
                "observation_end": common["target_end"],
            }
        )
    f = pd.DataFrame(forecasts)
    o = pd.DataFrame(outcomes)
    cases = []
    for ident, available in [("risk-full", o), ("risk-missing", o.iloc[:2])]:
        audit = define_call(
            "risk_audit", f, available, as_of=pd.Timestamp("2026-03-01", tz="UTC")
        )
        report = execute_call(audit)
        rows = []
        for row in report.rows.itertuples():
            rows.append(
                {
                    "clock": row.target_start.isoformat(),
                    "phase": "risk",
                    "predicted_variance": number(row.predicted_variance),
                    "realized_squared_residual": number(row.squared_residual),
                    "paired": bool(row.paired),
                }
            )
        selected = (
            report.summary.iloc[0]
            if ident == "risk-full"
            else report.cohorts.query("liquidity == 'illiquid'").iloc[0]
        )
        rows.append(
            {
                "clock": "2026-03-01T00:00:00+00:00",
                "phase": "aggregate" if ident == "risk-full" else "missing",
                **{
                    key: number(selected[key])
                    for key in [
                        "predicted_variance",
                        "realized_squared_residual",
                        "variance_ratio",
                        "coverage",
                    ]
                },
            }
        )
        case = scenario(
            ident,
            rows,
            {"runs": {"audit": audit}},
            ["packages/platform/src/quant_platform/analytics/risk_calibration.py"],
            owner_name="platform",
            certified=report.certified,
            real_calibration=report.real_calibration,
            independence_status=report.independence_status,
            sample_status=report.sample_status,
            summary=records(report.summary),
            cohorts=records(report.cohorts),
        )
        case["units"] = {
            "variance": "squared basis points over one-day target interval",
            "coverage": "paired rows / forecast rows",
            "variance_ratio": "dimensionless",
        }
        cases.append(case)
    return cases
