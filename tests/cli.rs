use std::process::Command;
#[test]
fn cli_emits_only_result_json_and_is_repeatable() {
    let output = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .args(["run", "fixtures/roundtrip.json"])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let result: serde_json::Value =
        serde_json::from_slice(&output.stdout).expect("stdout must contain only JSON");
    assert_eq!(result["equity"], "10019.78");
    let again = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .args(["run", "fixtures/roundtrip.json"])
        .output()
        .unwrap();
    assert_eq!(output.stdout, again.stdout);
}
#[test]
fn cli_errors_are_nonzero_and_leave_stdout_empty() {
    for args in [
        vec!["run", "does-not-exist.json"],
        vec!["unknown"],
        vec!["run"],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
            .args(args)
            .output()
            .unwrap();
        assert!(!output.status.success());
        assert!(output.stdout.is_empty());
        assert!(!output.stderr.is_empty());
    }
}
#[test]
fn cli_describes_explicit_capabilities() {
    let output = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .arg("capabilities")
        .output()
        .unwrap();
    assert!(output.status.success());
    let result: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert!(
        result["capabilities"]
            .as_array()
            .unwrap()
            .iter()
            .any(|c| c == "multi_asset")
    );
}

#[test]
fn cli_sizes_targets_without_executing_a_simulation() {
    let output = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .args(["size", "fixtures/sizing.json"])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let result: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(result["schema_version"], "sizing_result.v1");
    assert_eq!(result["projected_cash"], "9.01");
    assert_eq!(result["orders"][0]["quantity"], "99");
}
