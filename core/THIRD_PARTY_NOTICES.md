# Extracted quant-platform source

Source: https://github.com/runchengxie/quant-platform
Pinned revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
Original license: Apache-2.0, reproduced byte-for-byte in
licenses/quant-platform-Apache-2.0.txt. The source tree has no NOTICE file.

The original source and tests listed below retain their original license.
Engine packaging does not replace their attribution or original terms.
Changes: destination namespace, extraction of execution-integrity internal
helpers, import ordering/formatting, and new CostQuote/CostModel transport types.
Financial arithmetic, model conventions, return shapes and legacy clock
contracts are retained. Source consumer bindings remain on their old owner.

- packages/platform/src/quant_platform/backtest/market_paths.py → core/src/quant_backtest_core/backtest/market_paths.py (SHA256 0a2b71a3560259ab728f0ea48efea6d7de017e091f27536ae17d0239915fbad5)
- packages/platform/src/quant_platform/backtest/stress.py → core/src/quant_backtest_core/backtest/stress.py (SHA256 a90823cc48e32e9e60468992aa42de2892c3ace60e4c7c5a85176f107875de00)
- packages/platform/src/quant_platform/backtest/costs.py → core/src/quant_backtest_core/backtest/costs.py (SHA256 27d6d2d9b23dbd4664f99e36bbb5b3bef466a76dd7bab1c621716c277ce242a7)
- packages/platform/src/quant_platform/backtest/impact.py → core/src/quant_backtest_core/backtest/impact.py (SHA256 3efcab489722e2b287b4a55cdfded617b52414458adb514ccf4789f38c85c160)
- packages/platform/src/quant_platform/backtest/impact_scenarios.py → core/src/quant_backtest_core/backtest/impact_scenarios.py (SHA256 0b8c18b92d7e3fe462a5996d2eab498d55cb23b440345295e133cdd1ff64ef66)
- packages/platform/src/quant_platform/analytics/execution_integrity.py → core/src/quant_backtest_core/evidence/execution_integrity.py (SHA256 7b6d1fcaa1c79de49eb6d045695f49880f66fc991411984750d813cfa6bd2097)
- packages/platform/src/quant_platform/analytics/transaction_costs.py → core/src/quant_backtest_core/evidence/transaction_costs.py (SHA256 7631ff03107101ee7982e5166235620c137caf70cbd247600cd6cfbada4207f0)
- packages/platform/src/quant_platform/analytics/cost_scope.py → core/src/quant_backtest_core/evidence/cost_scope.py (SHA256 d523abacdace74c6dc465822afb25cd659d2e5d944e43d1a5cb13bf97c39bbfc)
- packages/platform/src/quant_platform/analytics/capital_returns.py → core/src/quant_backtest_core/evidence/capital_returns.py (SHA256 0a437b112a1beef1b228dbb99f07524c7b7324cbc13d8d99278298f4554d98f4)

Tests originate in tests/test_market_paths.py, test_transaction_costs.py, test_cost_scope.py, test_execution_integrity.py, test_impact_state.py, test_impact_optimization_scenarios.py, test_joint_stress.py (bars fixture: test_minute_execution.py), test_cost_evidence.py and test_capital_reconciliation.py at that same revision. Mixed planner/account integration tests remain at the source until their owner transfers.
