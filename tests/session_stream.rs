use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
fn request() -> Value {
    let t = 1735781400000000000_u64;
    json!({"schema_version":"engine_request.v2","currency":"CNY","price_basis":"raw","initial_cash":"10000","fee_bps":"10","enforce_t1":true,"instruments":[{"symbol":"AAA","price_precision":2,"buy_lot":100}],"required_capabilities":[],"sessions":[{"session_date":"2025-01-02","open_ts_ns":t,"valuation_ts_ns":t,"quotes":[{"symbol":"AAA","ts_ns":t,"bid":"10","ask":"10","bid_size":"1000","ask_size":"1000","tradable":true,"limit_up":false,"limit_down":false}],"orders":[{"id":"buy","symbol":"AAA","information_ts_ns":t-1,"side":"buy","quantity":"100"}]}]})
}
fn frames() -> Vec<String> {
    let mut config = request();
    let sessions = config.as_object_mut().unwrap().remove("sessions").unwrap();
    vec![json!({"schema_version":"engine_session_stream.v1","type":"start","sequence":0,"config":config}).to_string(), json!({"schema_version":"engine_session_stream.v1","type":"session","sequence":1,"session":sessions[0]}).to_string(), json!({"schema_version":"engine_session_stream.v1","type":"finish","sequence":2}).to_string()]
}
fn digest(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}
#[test]
fn real_binary_is_interactive_and_final_result_matches_v2() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
        .arg("session-stream")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let output = BufReader::new(child.stdout.take().unwrap());
    let (sender, receiver) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        for line in output.lines() {
            if sender.send(line).is_err() {
                break;
            }
        }
    });
    let read = || -> Value {
        serde_json::from_str(
            &receiver
                .recv_timeout(std::time::Duration::from_secs(20))
                .expect("response must arrive without closing stdin")
                .unwrap(),
        )
        .unwrap()
    };
    let frames = frames();
    writeln!(input, "{}", frames[0]).unwrap();
    input.flush().unwrap();
    let ready = read();
    assert_eq!(ready["type"], "ready");
    assert_eq!(ready["sequence"], 0);
    assert_eq!(ready["header_sha256"], digest(frames[0].as_bytes()));
    assert_eq!(ready["max_frame_bytes"], 67108864);
    writeln!(input, "{}", frames[1]).unwrap();
    input.flush().unwrap();
    let report = read();
    assert_eq!(report["type"], "session");
    assert_eq!(report["report"]["balance"]["cash"], "8999");
    let mut prefix = Sha256::digest(frames[0].as_bytes()).to_vec();
    prefix.extend(frames[1].as_bytes());
    assert_eq!(report["prefix_sha256"], digest(&prefix));
    writeln!(input, "{}", frames[2]).unwrap();
    drop(input);
    let finished = read();
    let mut final_prefix = Sha256::digest(&prefix).to_vec();
    final_prefix.extend(frames[2].as_bytes());
    assert_eq!(finished["prefix_sha256"], digest(&final_prefix));
    let request = serde_json::from_value(request()).unwrap();
    assert_eq!(
        finished["result"],
        serde_json::to_value(quant_backtest_engine::run_sessions(&request).unwrap()).unwrap()
    );
    assert!(child.wait().unwrap().success());
}
#[test]
fn real_binary_rejects_incomplete_and_invalid_streams() {
    let good = frames();
    let bad_session = good[1].replacen("\"sequence\":1", "\"sequence\":3", 1);
    let duplicate = good[0].replacen("\"sequence\":0", "\"sequence\":0,\"sequence\":0", 1);
    let unknown = good[0].replacen("{", "{\"unknown\":true,", 1);
    for lines in [
        vec![],
        vec![good[0].clone()],
        vec![good[0].clone(), good[1].clone()],
        vec![good[0].clone(), good[2].clone()],
        vec![
            good[0].clone(),
            good[1].clone(),
            good[2].clone(),
            good[2].clone(),
        ],
        vec![good[0].clone(), bad_session],
        vec![duplicate],
        vec![unknown],
        vec!["{bad}".into()],
        vec![good[0].clone(), good[0].clone()],
    ] {
        let mut child = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
            .arg("session-stream")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        {
            let mut input = child.stdin.take().unwrap();
            for line in lines {
                let _ = writeln!(input, "{line}");
            }
        }
        let result = child.wait_with_output().unwrap();
        assert!(!result.status.success());
        let text = String::from_utf8(result.stdout).unwrap();
        assert!(!text.contains("\"type\":\"finished\""));
    }
}

#[test]
fn real_binary_rejects_invalid_utf8_truncation_and_oversized_lines() {
    for bytes in [
        vec![0xff, b'\n'],
        frames()[0].as_bytes().to_vec(),
        vec![b' '; 67_108_865],
    ] {
        let mut child = Command::new(env!("CARGO_BIN_EXE_quant-backtest-engine"))
            .arg("session-stream")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let _ = child.stdin.take().unwrap().write_all(&bytes);
        let output = child.wait_with_output().unwrap();
        assert!(!output.status.success());
        assert!(output.stdout.is_empty());
    }
}
