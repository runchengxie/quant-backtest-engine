use anyhow::{Context, Result, bail};
use quant_backtest_engine::{
    Request,
    contract::CAPABILITIES,
    run, run_sessions,
    session_contract::{SESSION_CAPABILITIES, SessionRequest},
    sizing::{SizingRequest, size_targets},
    validation::{ValidationRejected, validate_reader},
};
use std::{
    env, fs,
    io::{self, Read, Write},
    process::ExitCode,
};
fn execute() -> Result<()> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    let output = match args.as_slice() {
        [command] | [command, _] if command == "depth-capabilities" => {
            serde_json::json!({"schema_version":"engine_depth_capabilities.v1","backend":"nautilus","backend_version":"0.66.0","capabilities":quant_backtest_engine::depth_contract::DEPTH_CAPABILITIES})
        }
        [command, path] if command == "depth" || command == "depth-validate" => {
            let mut bytes = Vec::new();
            fs::File::open(path)?
                .take(64 * 1024 * 1024 + 1)
                .read_to_end(&mut bytes)?;
            anyhow::ensure!(
                bytes.len() <= 64 * 1024 * 1024,
                "depth request exceeds 64 MiB"
            );
            let request: quant_backtest_engine::depth_contract::DepthRequest =
                serde_json::from_slice(&bytes)?;
            if command == "depth-validate" {
                request.validate()?;
                serde_json::json!({"schema_version":"engine_depth_validation.v1","backend":"nautilus","backend_version":"0.66.0","request_sha256":quant_backtest_engine::depth_contract::request_digest(&request)?,"capabilities":quant_backtest_engine::depth_contract::DEPTH_CAPABILITIES})
            } else {
                serde_json::to_value(quant_backtest_engine::run_depth(&request)?)?
            }
        }
        [command] if command == "session-stream" => {
            return quant_backtest_engine::session_stream::serve(
                io::BufReader::new(io::stdin()),
                io::stdout(),
            );
        }
        [command] if command == "capabilities" => {
            serde_json::json!({"schema_version":"engine_capabilities.v1","request_schema":"engine_request.v1","result_schema":"engine_result.v1","backend":"nautilus","backend_version":"0.66.0","capabilities":CAPABILITIES,"validator_version":1})
        }
        [command] if command == "session-capabilities" => {
            serde_json::json!({"schema_version":"engine_capabilities.v2","request_schema":"engine_request.v2","result_schema":"engine_result.v2","backend":"nautilus","backend_version":"0.66.0","capabilities":SESSION_CAPABILITIES})
        }
        [command, path] if command == "validate" => {
            let receipt = if path == "-" {
                validate_reader(io::stdin().lock())?
            } else {
                validate_reader(fs::File::open(path).context("cannot open request file")?)?
            };
            serde_json::to_value(receipt)?
        }
        [command, path] if command == "size" => {
            let bytes = fs::read(path).context("cannot read sizing file")?;
            let request: SizingRequest =
                serde_json::from_slice(&bytes).context("invalid sizing JSON")?;
            serde_json::to_value(size_targets(&request)?)?
        }
        [command, path] if command == "run" => {
            let bytes = fs::read(path).context("cannot read request file")?;
            let header: serde_json::Value =
                serde_json::from_slice(&bytes).context("invalid request JSON")?;
            if header
                .get("schema_version")
                .and_then(serde_json::Value::as_str)
                == Some("engine_request.v2")
            {
                let request: SessionRequest =
                    serde_json::from_slice(&bytes).context("invalid session request JSON")?;
                serde_json::to_value(run_sessions(&request)?)?
            } else {
                let request: Request =
                    serde_json::from_slice(&bytes).context("invalid request JSON")?;
                serde_json::to_value(run(&request)?)?
            }
        }
        _ => {
            bail!(
                "usage: quant-backtest-engine depth REQUEST.json | depth-validate REQUEST.json | depth-capabilities | validate REQUEST.json|- | run REQUEST.json | size SIZING.json | capabilities | session-capabilities"
            )
        }
    };
    let mut stdout = io::stdout().lock();
    serde_json::to_writer(&mut stdout, &output)?;
    writeln!(stdout)?;
    Ok(())
}
fn main() -> ExitCode {
    match execute() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("quant-backtest-engine: {e:#}");
            if e.is::<ValidationRejected>() {
                ExitCode::from(2)
            } else {
                ExitCode::FAILURE
            }
        }
    }
}
