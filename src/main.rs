use anyhow::{Context, Result, bail};
use quant_backtest_engine::{Request, contract::CAPABILITIES, run};
use std::{
    env, fs,
    io::{self, Write},
    process::ExitCode,
};
fn execute() -> Result<()> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    let output = match args.as_slice() {
        [command] if command == "capabilities" => {
            serde_json::json!({"schema_version":"engine_capabilities.v1","request_schema":"engine_request.v1","result_schema":"engine_result.v1","backend":"nautilus","backend_version":"0.66.0","capabilities":CAPABILITIES})
        }
        [command, path] if command == "run" => {
            let bytes = fs::read(path).context("cannot read request file")?;
            let request: Request =
                serde_json::from_slice(&bytes).context("invalid request JSON")?;
            serde_json::to_value(run(&request)?)?
        }
        _ => bail!("usage: quant-backtest-engine run REQUEST.json | capabilities"),
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
            ExitCode::FAILURE
        }
    }
}
