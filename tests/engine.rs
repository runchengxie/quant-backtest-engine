use quant_backtest_engine::{Request, run};
use serde_json::json;
use std::sync::Mutex;
static ENGINE: Mutex<()> = Mutex::new(());
fn fixture() -> Request {
    serde_json::from_str(include_str!("../fixtures/roundtrip.json")).unwrap()
}
#[test]
fn upstream_roundtrip_accounts_for_fees_and_no_lookahead() {
    let _guard = ENGINE.lock().unwrap_or_else(|e| e.into_inner());
    let r = run(&fixture()).unwrap();
    assert_eq!(r.cash, "10019.78");
    assert_eq!(r.equity, "10019.78");
    assert_eq!(r.commission, "0.22");
    assert_eq!(r.fills.len(), 2);
    assert_eq!(r.fills[0].price, "10");
    assert_eq!(r.fills[1].price, "12");
    assert_eq!(r.fills[1].ts_ns, 1735689601000000000);
    assert!(r.positions.is_empty());
}
#[test]
fn upstream_marks_open_positions_and_is_repeatable() {
    let _guard = ENGINE.lock().unwrap_or_else(|e| e.into_inner());
    let mut q = fixture();
    q.orders.truncate(1);
    let a = run(&q).unwrap();
    let b = run(&q).unwrap();
    assert_eq!(a, b);
    assert_eq!(a.cash, "9899.9");
    assert_eq!(a.positions_value, "110");
    assert_eq!(a.equity, "10009.9");
    assert_eq!(a.positions[0].quantity, "10");
}
#[test]
fn upstream_rejects_insufficient_cash_without_fabricated_fill() {
    let _guard = ENGINE.lock().unwrap_or_else(|e| e.into_inner());
    let mut q = fixture();
    q.orders.truncate(1);
    q.initial_cash = "1.00".into();
    let a = run(&q).unwrap();
    assert!(a.fills.is_empty());
    assert_eq!(a.cash, "1");
    assert!(matches!(a.orders[0].status.as_str(), "DENIED" | "REJECTED"));
}
#[test]
fn orders_without_a_later_quote_remain_unsubmitted() {
    let _guard = ENGINE.lock().unwrap_or_else(|e| e.into_inner());
    let mut q = fixture();
    q.orders.truncate(1);
    q.orders[0].information_ts_ns = q.quotes.last().unwrap().ts_ns;
    let a = run(&q).unwrap();
    assert!(a.fills.is_empty());
    assert_eq!(a.orders[0].status, "NOT_SUBMITTED");
}
#[test]
fn multiple_assets_use_individual_marks() {
    let _guard = ENGINE.lock().unwrap_or_else(|e| e.into_inner());
    let mut v = serde_json::to_value(fixture()).unwrap();
    v["fee_bps"] = json!("0");
    v["orders"].as_array_mut().unwrap().truncate(1);
    v["instruments"]
        .as_array_mut()
        .unwrap()
        .push(json!({"symbol":"BBB","price_precision":2}));
    v["quotes"]
        .as_array_mut()
        .unwrap()
        .push(json!({"symbol":"BBB","ts_ns":1735689603000000000_u64,"bid":"20.00","ask":"20.00"}));
    v["orders"].as_array_mut().unwrap().push(json!({"id":"buy-b","symbol":"BBB","information_ts_ns":1735689600000000000_u64,"side":"buy","quantity":"5"}));
    let a = run(&serde_json::from_value(v).unwrap()).unwrap();
    assert_eq!(a.cash, "9800");
    assert_eq!(a.positions_value, "210");
    assert_eq!(a.equity, "10010");
    assert_eq!(a.positions.len(), 2);
}
