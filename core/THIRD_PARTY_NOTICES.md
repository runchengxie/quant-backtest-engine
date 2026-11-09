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

## Complete minute financial owner (Task 5)

The following Apache-2.0 source bodies transfer together. Changes are namespace,
provenance, import/formatting and checkpoint schema `minute-session.v2` to
`minute-session.v3`. Original checkpoints remain on the pinned Platform owner.

- packages/platform/src/quant_platform/backtest/minute.py → core/src/quant_backtest_core/backtest/minute.py (SHA256 82e0041c16c53b4f7a3f181fcb3e07233a15da39e4c1869597f205a712728814)
- packages/platform/src/quant_platform/backtest/minute_session.py → core/src/quant_backtest_core/backtest/minute_session.py (SHA256 0872227f551639c1b75ef84119691e4c92171c7c3af16ff55a95c45452ee7039)
- packages/platform/src/quant_platform/backtest/_minute_checkpoint.py → core/src/quant_backtest_core/backtest/_minute_checkpoint.py (SHA256 f75937e47a26eacc2d0ec3ef228669580a0e6cdb156af0c4841aa0212dd43542)
- packages/platform/src/quant_platform/backtest/quantity_locks.py → core/src/quant_backtest_core/backtest/quantity_locks.py (SHA256 743767b66958def9b0b424747058906039a9da4e6126e06f25a340d19ca66435)
- packages/platform/src/quant_platform/_portfolio/minute_execution.py → core/src/quant_backtest_core/_minute/minute_execution.py (SHA256 ea4e3d1db80b90647185942d2de6935f57f29db569ab9e4b4070d210b3654bb9)
- packages/platform/src/quant_platform/_portfolio/_minute_state.py → core/src/quant_backtest_core/_minute/_minute_state.py (SHA256 a14428a9ea216697a77dee31bd35389988afcde73442976e3eb58973114f777b)
- packages/platform/src/quant_platform/_portfolio/_minute_validation.py → core/src/quant_backtest_core/_minute/_minute_validation.py (SHA256 a7c6f3784db7e22b7ec424d912c5eeaadcb9522f8da2a92d5a767ca30662b471)
- packages/platform/src/quant_platform/_portfolio/capital_flows.py → core/src/quant_backtest_core/_minute/capital_flows.py (SHA256 403eb8714b07141609a879b276f3b1aa171838a088e111c2a3f1095f26051664)
- packages/platform/src/quant_platform/_portfolio/corporate_actions.py → core/src/quant_backtest_core/_minute/corporate_actions.py (SHA256 2c6fd0e45636c15c37bebee7b5037f0607b8a4cf169d6cf20fe5da54e1b64eaa)
- packages/platform/src/quant_platform/_portfolio/valuation_events.py → core/src/quant_backtest_core/_minute/valuation_events.py (SHA256 57feba201db8f16b6397e7e9ad1051b9f2b112a50afc28aa8e9bd3f629edaab9)

Transferred test oracles: test_minute_execution.py, test_minute_execution_feedback.py,
test_minute_execution_hardening.py, test_minute_execution_mark_provenance.py,
test_minute_execution_valuation_events.py, test_minute_session.py,
test_minute_session_actions.py and test_quantity_locks.py, all from the same revision.

# Deterministic simulator extraction (Task 8)

Original source: [quant-platform](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/packages/microstructure).
Pinned source revision: `7a618bddd8fdeee5dbe37fe5b54a9698e0de5355`.
Original license: Apache-2.0; original LICENSE is reproduced without modification.
No source NOTICE file exists. Native `src/lib.rs`, Cargo.lock and the Python stub
retain their original bytes and arithmetic. Only package license metadata changes.
Distribution `quant-microstructure-core` and module `_microstructure_rs` remain unchanged.
Python simulator arithmetic and event contracts retain their original bodies; replay
adds two union type annotations and formatting to satisfy Engine type/style checks.
Imports of transferred tests
use the new namespace. Learned generators and training remain in Platform.

- packages/microstructure/src/ticknet/simulator/matching.py → core/src/quant_backtest_core/microstructure/matching.py (SHA256 920adb6b3f5196512cbf23692ab6dbfd7f980b5a80e965a2854d7cf60c216e2a)
- packages/microstructure/src/ticknet/simulator/pack.py → core/src/quant_backtest_core/microstructure/pack.py (SHA256 d9b049c508d005fac34c0d70505de8932b8548eb44a570847f820c0435a01f2b)
- packages/microstructure/src/ticknet/simulator/ordering.py → core/src/quant_backtest_core/microstructure/ordering.py (SHA256 d5744eba37df981d3af9bd7fabc5dffb0d3afa095b2ca76eb109fe927f13db84)
- packages/microstructure/src/ticknet/simulator/replay.py → core/src/quant_backtest_core/microstructure/replay.py (SHA256 10c4228a88dfca9d2962af4c7326bfc8cf2253866027da9ae3f787504694cc2b)
- packages/microstructure/src/ticknet/simulator/correctness.py → core/src/quant_backtest_core/microstructure/correctness.py (SHA256 a738a674124f82390d40e15c438092edd8c3c70ca3bfaf08f2192da7668d9a3d)

## Account feedback, reservations and execution impact (Task 9)

Original source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, Apache-2.0.
The license above remains applicable. No original NOTICE file exists. Account
and impact bodies are preserved; account/composite checkpoint schema identities
change to 2 / execution-state.v2. Pending changes replace concrete research
optimizer coupling with a structural caller-owned protocol and execution-only
validation. No OSQP, generic optimization or learned-model code transfers.

- packages/platform/src/quant_platform/backtest/paper_account.py → core/src/quant_backtest_core/backtest/paper_account.py (SHA256 244cb0e51d41aefb555adf106c3967ab731cac7f02911303bb460e5f0b7df4c9)
- packages/platform/src/quant_platform/backtest/account_events.py → core/src/quant_backtest_core/backtest/account_events.py (SHA256 806730fe7f9905842731dbd8d6f18cfec136b7bef5c42739851e7802e3a3e399)
- packages/platform/src/quant_platform/backtest/_account_event_types.py → core/src/quant_backtest_core/backtest/_account_event_types.py (SHA256 fdc4f4519bc900dcd08d5388d2f3d4ed3bdc5a42315079599f4e16f783093bf2)
- packages/platform/src/quant_platform/backtest/checkpoints.py → core/src/quant_backtest_core/backtest/checkpoints.py (SHA256 f7ea03dd0d9e96e6348525bb9cc6c9f91eb0800fd65efa6a8b1da9553c424d2b)
- packages/platform/src/quant_platform/backtest/reconciliation.py → core/src/quant_backtest_core/backtest/reconciliation.py (SHA256 0065757d0ca45de40836a787686daef413806689c00f49e21dd24280ddd038f8)
- packages/platform/src/quant_platform/portfolio/pending_allocation.py → core/src/quant_backtest_core/planning/pending_allocation.py (SHA256 a3af30230f2b1d84681782d43faa5c2b061c4ec7941496bb164718843e8538a0)
- packages/microstructure/src/ticknet/simulator/impact.py → core/src/quant_backtest_core/microstructure/impact.py (SHA256 afce487bad76d2db22e8520c56f9589aab3621be860bc3c5283d4fe150551fdd)

Tests: original test_account_events.py, test_paper_account.py, test_capital_reconciliation.py, test_composite_checkpoint.py, test_pending_allocation.py; all eleven microstructure/test_impact.py cases, two test_replay_clock.py impact admission cases and test_rust_parity.py native impact rejection. Pending tests replace only research coupling with literal execution-only fixtures; original optimizer parity runs separately against its frozen environment.
