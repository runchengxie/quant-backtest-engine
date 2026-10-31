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

#[test]
fn cli_dispatches_session_schema_without_changing_legacy_run() {
    let output = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .args(["run", "fixtures/sessions.json"])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let result: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(result["schema_version"], "engine_result.v2");
    assert_eq!(result["final_nav"], "10197.8");
    assert_eq!(result["daily_ledger"].as_array().unwrap().len(), 2);
}

fn validate_stdin(bytes: &[u8]) -> std::process::Output {
    use std::io::Write;
    use std::process::Stdio;
    let mut child = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .args(["validate", "-"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let _ = child.stdin.take().unwrap().write_all(bytes);
    child.wait_with_output().unwrap()
}

#[test]
fn cli_validates_exact_bytes_without_simulation() {
    let bytes = std::fs::read("fixtures/roundtrip.json").unwrap();
    let output = validate_stdin(&bytes);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let receipt: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(receipt["schema_version"], "engine_validation.v1");
    assert_eq!(receipt["validator_version"], 1);
    assert_eq!(receipt["request_schema"], "engine_request.v1");
    assert_eq!(receipt["valid"], true);
    assert_eq!(receipt["input_sha256"].as_str().unwrap().len(), 64);
    let file = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .args(["validate", "fixtures/roundtrip.json"])
        .output()
        .unwrap();
    assert_eq!(output.stdout, file.stdout);
    let mut changed = bytes.clone();
    changed.push(b' ');
    let changed = validate_stdin(&changed);
    let changed: serde_json::Value = serde_json::from_slice(&changed.stdout).unwrap();
    assert_ne!(receipt["input_sha256"], changed["input_sha256"]);
    let caps = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .arg("capabilities")
        .output()
        .unwrap();
    let caps: serde_json::Value = serde_json::from_slice(&caps.stdout).unwrap();
    assert_eq!(caps["validator_version"], 1);
}

#[test]
fn cli_rejects_invalid_semantics_and_oversize_with_distinct_status() {
    let base: serde_json::Value =
        serde_json::from_slice(&std::fs::read("fixtures/roundtrip.json").unwrap()).unwrap();
    let mut variants = vec![b"{".to_vec(), vec![b' '; 1024 * 1024 + 1]];
    for field in [
        "capability",
        "duplicate",
        "chronology",
        "crossed",
        "decimal",
    ] {
        let mut value = base.clone();
        match field {
            "capability" => value["required_capabilities"] = serde_json::json!(["unknown"]),
            "duplicate" => value["orders"][1]["id"] = value["orders"][0]["id"].clone(),
            "chronology" => value["quotes"][1]["ts_ns"] = serde_json::json!(1),
            "crossed" => value["quotes"][0]["bid"] = serde_json::json!("11.00"),
            _ => value["initial_cash"] = serde_json::json!("999999999999999999999999999999999999"),
        }
        variants.push(serde_json::to_vec(&value).unwrap());
    }
    for bytes in variants {
        let output = validate_stdin(&bytes);
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        assert!(!output.stderr.is_empty());
    }
    let output = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .args(["validate", "absent.json"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
}
