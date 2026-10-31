//! Independent backtest request boundary and upstream adapter.
pub mod contract;
pub use contract::{BacktestResult, Request};

mod nautilus;
mod strategy;

/// Executes one request on a fresh thread, isolating upstream thread-local state.
/// This is a synchronous API; use separate CLI processes for resource isolation.
pub fn run(request: &Request) -> anyhow::Result<BacktestResult> {
    request.validate()?;
    let request = request.clone();
    std::thread::spawn(move || nautilus::execute(&request))
        .join()
        .map_err(|_| anyhow::anyhow!("upstream engine panicked"))?
}

pub mod sizing;
