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

pub mod session_contract;
mod session_strategy;
mod sessions;
pub fn run_sessions(
    request: &session_contract::SessionRequest,
) -> anyhow::Result<session_contract::SessionResult> {
    request.validate()?;
    let request = request.clone();
    std::thread::spawn(move || sessions::execute(&request))
        .join()
        .map_err(|_| anyhow::anyhow!("upstream session engine panicked"))?
}

pub mod validation;

/// Development-only wall measurements; no changes to the request/result wire schemas.
/// Matching and accounting are measured together inside upstream replay.
pub fn run_sessions_profiled(
    request: &session_contract::SessionRequest,
) -> anyhow::Result<(session_contract::SessionResult, SessionTimings)> {
    let started = std::time::Instant::now();
    request.validate()?;
    let request = request.clone();
    let validation_clone_seconds = started.elapsed().as_secs_f64();
    let (result, mut timings) = std::thread::spawn(move || sessions::execute_profiled(&request))
        .join()
        .map_err(|_| anyhow::anyhow!("upstream session engine panicked"))??;
    timings.validation_clone_seconds = validation_clone_seconds;
    Ok((result, timings))
}
pub use sessions::SessionTimings;

/// Replays owned whole sessions on one dedicated upstream worker thread.
/// The source is pulled only after the preceding session replay and snapshot.
/// Errors discard the final result. Quotes and admission rules are retained for
/// one session; final reports, intent metadata and upstream histories grow.
pub fn run_sessions_iter<I>(
    config: session_contract::SessionConfig,
    sessions: I,
) -> anyhow::Result<session_contract::SessionResult>
where
    I: Iterator<Item = anyhow::Result<session_contract::MarketSession>> + Send + 'static,
{
    std::thread::spawn(move || sessions::execute_iter(config, sessions))
        .join()
        .map_err(|_| anyhow::anyhow!("upstream session engine panicked"))?
}
