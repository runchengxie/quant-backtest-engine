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

## Task 10 bounded planning and actual fill allocation

Copyright 2026 runchengxie. Apache-2.0 source from quant-platform
`7a618bddd8fdeee5dbe37fe5b54a9698e0de5355`; original license retained in
`licenses/quant-platform-Apache-2.0.txt`. Changes: namespace/provenance only for
the five kernels; test imports/formatting and two approved minute fixture ports.
Arithmetic, solver, rounding, statuses and original economic assertions retained.

- `packages/platform/src/quant_platform/portfolio/impact_planning.py` → `src/quant_backtest_core/planning/impact_planning.py`; original SHA256 `f7aaf8cd7b778fcd394ef08fb66e34245c78976543d7b9493f1c303eaa7e6359`.
- `packages/platform/src/quant_platform/portfolio/multiperiod.py` → `src/quant_backtest_core/planning/multiperiod.py`; original SHA256 `1ea34f11c9dbab02ea6560f983918ae1f418c5f40025f7faaafe14527ff94845`.
- `packages/platform/src/quant_platform/portfolio/discrete_inventory.py` → `src/quant_backtest_core/planning/discrete_inventory.py`; original SHA256 `3238ecae91588ae6818f718af8938ecefc506ae2e357c5627644f07ed982bd58`.
- `packages/platform/src/quant_platform/portfolio/discrete_oracle.py` → `src/quant_backtest_core/planning/discrete_oracle.py`; original SHA256 `98aac895872f1f86536f7739852a02110c8ffd40532157d26009f81c3139a7b0`.
- `packages/platform/src/quant_platform/portfolio/sleeve_allocation.py` → `src/quant_backtest_core/planning/sleeve_allocation.py`; original SHA256 `6916287aed000cc3a6d349c8ce83ae2c4ee6d43158333eddbf68b56eb7d83577`.
- `tests/test_impact_planning.py`; original SHA256 `c5dd8869e88561383a26e6dafacd68fba58ca752fc2cc1e60ccccad7ffe7ef21`; complete suite transferred.
- `tests/test_multiperiod.py`; original SHA256 `f0316583b6c097642cd281a500ddd08d25c94a32ad571ad502002d12a51de712`; complete suite transferred.
- `tests/test_discrete_inventory.py`; original SHA256 `5f45ba0cd9aeb845c274d0728492a3566b2ce097c222e1894ac1e6d896b4cf01`; complete suite transferred.
- `tests/test_sleeve_allocation.py`; original SHA256 `ec6025a7ca294861a23427f0a89826f16e83d206e302f51ee7c8a741f3086989`; complete suite transferred.
- `tests/test_impact_optimization_scenarios.py`; original SHA256 `b5a970b71f410d735ee2a5b53f908d1442317a84f3519f5969866f49890fc586`; five finite-oracle functions only; permanent checks already owned and general risk optimizer remains Platform.

## Task 13 daily metadata and pure configuration

Copyright 2026 runchengxie. Apache-2.0 source at quant-platform
`7a618bddd8fdeee5dbe37fe5b54a9698e0de5355`; license retained above.

- `packages/platform/src/quant_platform/_portfolio/execution_sim/config.py`
  is transferred to `daily/execution_sim/config.py` unchanged except provenance comments.
  Its exact original SHA256 is recorded in the destination header.
- `packages/platform/src/quant_platform/_portfolio/execution_calendar.py`
  supplies inclusive filtering and <=0/positive shift arithmetic. The new
  `daily/calendar.py` uses only explicit sessions, without provider/future fallbacks.
- `_portfolio/_metrics_period.py` supplies the product-minus-one return convention.
  `daily/summary.py` requires complete explicit valuation/zero-flow evidence and
  preserves unknown rows; broad research statistics remain Platform.

## Task 14 daily financial owner (Apache-2.0)

Transferred from quant-platform at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355. Original license is retained in licenses/quant-platform-Apache-2.0.txt.
Financial arithmetic, result tables and direct API signatures are retained. Calendar acquisition, strategy selection, weight-model construction, broad research statistics and publication remain Platform. The new neutral request, wire and summary adapter do not manufacture missing evidence.

- packages/platform/src/quant_platform/_portfolio/execution_sim/core.py → core/src/quant_backtest_core/daily/execution_sim/core.py (SHA256 c8584e014c67084a1220378de24639797037a0fbfe093ff445920a55004579ab)
- packages/platform/src/quant_platform/_portfolio/execution_sim/models.py → core/src/quant_backtest_core/daily/execution_sim/models.py (SHA256 d1d81afa8b0dd7eacf36efe8c75b95a38f4714069bfbbd982692a6ab3e67edb0)
- packages/platform/src/quant_platform/_portfolio/execution_sim/capacity.py → core/src/quant_backtest_core/daily/execution_sim/capacity.py (SHA256 d693c1643111b9f283f14cb77f3867dd79fd03727ece431eab5e4aac58ed5622)
- packages/platform/src/quant_platform/_portfolio/execution_sim/capacity_simulation.py → core/src/quant_backtest_core/daily/execution_sim/capacity_simulation.py (SHA256 72b42804270373a878c54f63020340fda4c9f52afcea2d3387a5d741c487a44f)
- packages/platform/src/quant_platform/_portfolio/execution_sim/adjusted_nav.py → core/src/quant_backtest_core/daily/execution_sim/adjusted_nav.py (SHA256 40e2871c9da64456bbc7c06ce052123c5f06e77a700709b2eb94dc491c49b391)
- packages/platform/src/quant_platform/_portfolio/execution_sim/ideal_nav.py → core/src/quant_backtest_core/daily/execution_sim/ideal_nav.py (SHA256 b0ef7bc059905b36139bb48c933e9ce8683dd9f7925ff98767c7fb887c590ed6)
- packages/platform/src/quant_platform/_portfolio/execution_sim/orders.py → core/src/quant_backtest_core/daily/execution_sim/orders.py (SHA256 39d48581f0de61f7ba65e2a5421cd85706ff7537725ef34e77b6bd9b74630b66)
- packages/platform/src/quant_platform/_portfolio/execution_sim/orders_ideal.py → core/src/quant_backtest_core/daily/execution_sim/orders_ideal.py (SHA256 ca5f237ee87bfa3266b8127f4d6d689743092a4ed3eed7bf260fcf566b2962c6)
- packages/platform/src/quant_platform/_portfolio/execution_sim/orders_nav.py → core/src/quant_backtest_core/daily/execution_sim/orders_nav.py (SHA256 524cbc6ced909e617976b2ddb0086c39edc8ed55831c34541554583be8837b8d)
- packages/platform/src/quant_platform/_portfolio/execution_sim/orders_nav_fees.py → core/src/quant_backtest_core/daily/execution_sim/orders_nav_fees.py (SHA256 014cc21abff0bbdcc66cd5c0bbdbd2a47afb071526e5d4553ca7bf514540d1b9)
- packages/platform/src/quant_platform/_portfolio/execution_sim/orders_nav_quantities.py → core/src/quant_backtest_core/daily/execution_sim/orders_nav_quantities.py (SHA256 19515ea818e424bd83ac9dc172fc3db80a5ddb638a2406086eeef949bd0eead0)
- packages/platform/src/quant_platform/_portfolio/execution_sim/orders_nav_states.py → core/src/quant_backtest_core/daily/execution_sim/orders_nav_states.py (SHA256 1f7fdb9d9068aa89f2d5da837b0c226db3b2c4ade0121f6b988768c40a099703)
- packages/platform/src/quant_platform/_portfolio/execution_sim/orders_targets.py → core/src/quant_backtest_core/daily/execution_sim/orders_targets.py (SHA256 8461f81ec5f54a31eaa5105428927dbbc6230929b073558ab5760cf6b8ebea1b)
- packages/platform/src/quant_platform/_portfolio/execution_sim/reporting.py → core/src/quant_backtest_core/daily/execution_sim/reporting.py (SHA256 2adf4c0040a2a78fa158964baddd4cd19fac93a036f73df714323acb3a3eedc5)
- packages/platform/src/quant_platform/_portfolio/execution_sim/results.py → core/src/quant_backtest_core/daily/execution_sim/results.py (SHA256 ca82988311f276c785a23a78f4022e0438face2e19e5db3edec29e6ba944fa46)
- packages/platform/src/quant_platform/_portfolio/execution_sim/table_preparation.py → core/src/quant_backtest_core/daily/execution_sim/table_preparation.py (SHA256 fa666fdbf7c7714150720f329e33a616a9c4150df7b9098aaefbee2a09e1c886)
- packages/platform/src/quant_platform/_portfolio/execution_sim/corporate_actions.py → core/src/quant_backtest_core/daily/execution_sim/corporate_actions.py (SHA256 8206e2011847d91ba9b7c03a34468f901cc27ada62de37280a32f31e0772e098)
- packages/platform/src/quant_platform/_portfolio/execution_sim/cost_evidence.py → core/src/quant_backtest_core/daily/execution_sim/cost_evidence.py (SHA256 1eefd915b59fc5ea30e52cef144019478c66d42173f3af9a6a3b3b49a3c54dee)
- packages/platform/src/quant_platform/_portfolio/execution_sim/delisting.py → core/src/quant_backtest_core/daily/execution_sim/delisting.py (SHA256 e5ccba226b93860a12e4d35d44a8ea391f72f7e80e5fb8ffad0e865e2e1c205c)
- packages/platform/src/quant_platform/_portfolio/_execution_models.py → core/src/quant_backtest_core/daily/_execution_models.py (SHA256 c5965d67642589c01690b82b278f493fecfb07b67c6ca8c39aec4318bd187e86)
- packages/platform/src/quant_platform/_portfolio/_execution_build.py → core/src/quant_backtest_core/daily/_execution_build.py (SHA256 15f46e950d78a999404f7a3499467861e64213f5238200df24824b4f99a9d0cf)
- packages/platform/src/quant_platform/_portfolio/dated_fees.py → core/src/quant_backtest_core/daily/dated_fees.py (SHA256 1c1e54bf8adaf096eeb91a72d413ddea8efbb7768f35dde2ad684ddab9062611)
- packages/platform/src/quant_platform/_portfolio/turnover.py → core/src/quant_backtest_core/daily/turnover.py (SHA256 03a8bd8a5ee9dba5af305dc5d43d61d71bc62170ffc0bd433a92decfc423cc4d)
- packages/platform/src/quant_platform/_portfolio/execution.py → core/src/quant_backtest_core/daily/execution.py (SHA256 c6a0394279f8e546b21b5fed5fdcec041b7485547fb4e4760f309a8c0730eb99)
- packages/platform/src/quant_platform/_portfolio/backends/trade_accounting.py → core/src/quant_backtest_core/daily/trade_accounting.py (SHA256 c11393d6356292609a0ff3c2c266aede592a7e784c9cb8f2ff5b72979862e4b8)
- packages/platform/src/quant_platform/backtest/ledger.py → core/src/quant_backtest_core/backtest/ledger.py (SHA256 64e80a2067de8c729e5b55b798084dc62567f3c43fac1e6acc5e6d9aac6741ec)
- packages/platform/src/quant_platform/_portfolio/types.py → core/src/quant_backtest_core/daily/types.py (SHA256 b19bd59ad3ae348c040ae20b6837f276c901d90ebb20a5e156ab51c430b49f9e)
- packages/platform/src/quant_platform/_portfolio/execution_calendar.py → core/src/quant_backtest_core/daily/_calendar_values.py (SHA256 3d7d0ea78c6ad6afe75df044641e8005d0c094d6fc91525e50e189bce7b13d10)
- packages/platform/src/quant_platform/_portfolio/execution_sim/__init__.py → core/src/quant_backtest_core/daily/execution_sim/__init__.py (SHA256 90ec8b66be3a3a45a1a14a7c47515c7f00cdd3833efbe79b2502fea0c134263f)
- packages/platform/src/quant_platform/_portfolio/_position_backtest_config.py → core/src/quant_backtest_core/daily/_position_backtest_config.py (SHA256 3fd7cb813a59ee9e0e65a30c78e82a92db8e71f05f3416decb4d4d5c68333534)
- packages/platform/src/quant_platform/_portfolio/_position_backtest_engine.py → core/src/quant_backtest_core/daily/_position_backtest_engine.py (SHA256 f9bcd4a08d9222ad3719a8b229a26a58300995a1fe69da785736d54790a772af)
- packages/platform/src/quant_platform/_portfolio/contracts.py → core/src/quant_backtest_core/daily/_position_validation.py (SHA256 e4756d97cd169612398097c8d2de08b7954d23f01b0454624899330f8c1b8441)
- packages/platform/src/quant_platform/_portfolio/portfolio_weights.py → core/src/quant_backtest_core/daily/_period_helpers.py (SHA256 55f35fa40221abbd9c55296731e91bf63573ebb93731cf6df976d7b395a8cd4b)
- packages/platform/src/quant_platform/_portfolio/leg_helpers.py → core/src/quant_backtest_core/daily/_period_helpers.py (SHA256 21c0acfc87492341c3381f29bd71503e58ac587dd57b0e160b5e889055d38c52)
