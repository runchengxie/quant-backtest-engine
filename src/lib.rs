//! Independent backtest request boundary and upstream adapter.
pub mod contract;
pub use contract::{BacktestResult, Request};

/// Executes a validated request using the upstream backtest engine.
pub fn run(_request: &Request) -> anyhow::Result<BacktestResult> {
    anyhow::bail!("adapter not implemented")
}
