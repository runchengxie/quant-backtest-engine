use quant_backtest_engine::Request;
use serde_json::{Value, json};

fn fixture() -> Value {
    json!({"schema_version":"engine_request.v1", "initial_cash":"10000.00", "fee_bps":"0",
        "instruments":[{"symbol":"AAA", "price_precision":2}],
        "quotes":[{"symbol":"AAA","ts_ns":1735689600000000000_u64,"bid":"10.00","ask":"10.00"}],
        "orders":[{"id":"buy-1","symbol":"AAA","information_ts_ns":1735689599999999999_u64,"side":"buy","quantity":"10"}],
        "required_capabilities":[]})
}
fn valid(value: Value) -> bool {
    serde_json::from_value::<Request>(value).is_ok_and(|r| r.validate().is_ok())
}
#[test]
fn accepts_explicit_time_and_decimal_request() {
    assert!(valid(fixture()));
}
#[test]
fn rejects_unknown_fields_and_schema() {
    let mut v = fixture();
    v["surprise"] = json!(true);
    assert!(!valid(v));
    let mut v = fixture();
    v["schema_version"] = json!("engine_request.v999");
    assert!(!valid(v));
}
#[test]
fn rejects_unsupported_rules() {
    let mut v = fixture();
    v["required_capabilities"] = json!(["a_share_t_plus_one"]);
    assert!(!valid(v));
}
#[test]
fn rejects_invalid_financial_values() {
    for (field, values) in [
        (
            "initial_cash",
            vec!["0", "-1", "NaN", "999999999999999999999999999999999999"],
        ),
        ("fee_bps", vec!["-1", "10001", "inf"]),
    ] {
        for value in values {
            let mut v = fixture();
            v[field] = json!(value);
            assert!(!valid(v), "{field}={value}");
        }
    }
    for value in ["0", "-2", "1.5", "99999999999999999999"] {
        let mut v = fixture();
        v["orders"][0]["quantity"] = json!(value);
        assert!(!valid(v));
    }
    for value in ["0", "-1", "10.001", "NaN"] {
        let mut v = fixture();
        v["quotes"][0]["bid"] = json!(value);
        assert!(!valid(v));
    }
}
#[test]
fn rejects_ambiguous_or_unknown_identifiers() {
    for key in ["instruments", "orders"] {
        let mut v = fixture();
        let item = v[key][0].clone();
        v[key].as_array_mut().unwrap().push(item);
        assert!(!valid(v));
    }
    for symbol in ["", "AAA.SIM", "has space", "非标"] {
        let mut v = fixture();
        v["instruments"][0]["symbol"] = json!(symbol);
        assert!(!valid(v));
    }
    let mut v = fixture();
    v["orders"][0]["symbol"] = json!("UNKNOWN");
    assert!(!valid(v));
}
#[test]
fn rejects_unordered_ticks_and_crossed_quotes() {
    let mut v = fixture();
    let q = v["quotes"][0].clone();
    v["quotes"].as_array_mut().unwrap().push(q);
    assert!(!valid(v));
    let mut v = fixture();
    v["quotes"][0]["bid"] = json!("11.00");
    assert!(!valid(v));
    let mut v = fixture();
    v["quotes"][0]["ts_ns"] = json!(0);
    assert!(!valid(v));
}
