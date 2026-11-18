//! Nonwire development runner. Durations are wall time, never performance assertions.
use anyhow::{Context, Result};
use quant_backtest_engine::{
    run_sessions_profiled,
    session_contract::SessionRequest,
    sizing::{SizingRequest, size_targets},
};
use std::{
    env, fs,
    io::{self, Write},
    time::Instant,
};
fn main() -> Result<()> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    anyhow::ensure!(
        (1..=2).contains(&args.len()),
        "usage: profile_sessions REQUEST.json [SIZING.json]"
    );
    let started = Instant::now();
    let bytes = fs::read(&args[0]).context("read request")?;
    let request: SessionRequest = serde_json::from_slice(&bytes)?;
    let input_read_decode_seconds = started.elapsed().as_secs_f64();
    let sizing = if let Some(path) = args.get(1) {
        let request: SizingRequest = serde_json::from_slice(&fs::read(path)?)?;
        let started = Instant::now();
        let result = size_targets(&request)?;
        Some(serde_json::json!({"seconds": started.elapsed().as_secs_f64(), "result": result}))
    } else {
        None
    };
    let started = Instant::now();
    let (result, phases) = run_sessions_profiled(&request)?;
    let execution_seconds = started.elapsed().as_secs_f64();
    let started = Instant::now();
    let result_bytes = serde_json::to_vec(&result)?;
    let result_serialization_seconds = started.elapsed().as_secs_f64();
    let output = serde_json::json!({"schema_version":"session_profile.v1", "input_read_decode_seconds":input_read_decode_seconds,"execution_seconds":execution_seconds,"phases":phases,"result_serialization_seconds":result_serialization_seconds,"sizing":sizing,"result":serde_json::from_slice::<serde_json::Value>(&result_bytes)?});
    serde_json::to_writer(io::stdout().lock(), &output)?;
    io::stdout().write_all(b"\n")?;
    Ok(())
}
