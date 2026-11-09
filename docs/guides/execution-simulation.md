# Capacity and daily NAV execution simulation

[中文](execution-simulation.zh-CN.md)

The implemented Task 13 surface is [daily input metadata, supplied calendars,
pure configuration and financial evidence summaries](../product/daily-inputs.md).
Daily execution and its full financial tables remain pending Task 14; this page
preserves the promised destination and anchors without claiming an executable backend.

## Public API

Use the daily leaf modules described in [daily inputs](../product/daily-inputs.md).
The SDK declares `daily-input.v1` pending and rejects executable admission.

## Configuration

The original `ExecutionSimConfig` and pure parser are available in
`quant_backtest_core.daily.execution_sim.config`. Their source arithmetic and
parser behavior remain unchanged.

## Inputs and outputs

The neutral request requires explicit units, selectors, clocks and supplied dates.
The conservative summary preserves unknown values. It does not replace the
original financial tables or Platform research statistics.

## Delisting audit

Full owner behavior and table parity are pending Task 14. No new delisting
model or inferred data is introduced by the metadata seam.

## Corporate actions and price units

Nonempty action requests require raw prices and the existing action class.
New neutral empty actions mean no request; direct legacy empty opt-in is preserved.
See [the precise unit and action contract](../product/daily-inputs.md).

## Interpreting the paths

Each run will have one financial owner. Task 13 does not execute a path,
reconstruct research metrics or publish evidence of prospective alpha.
Provider C release and compatible consumer migration remain pending.
