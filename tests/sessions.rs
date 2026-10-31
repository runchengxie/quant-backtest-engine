use quant_backtest_engine::{run_sessions, session_contract::SessionRequest};
use serde_json::{Value, json};
fn fixture() -> Value {
    let t = 1735781400000000000_u64; // 2025-01-02 09:30 Asia/Shanghai
    let quote = |ts: u64, p: &str| json!({"symbol":"AAA","ts_ns":ts,"bid":p,"ask":p,"bid_size":"1000000","ask_size":"1000000","tradable":true,"limit_up":false,"limit_down":false});
    json!({"schema_version":"engine_request.v2","currency":"CNY","price_basis":"raw","initial_cash":"10000","fee_bps":"10","enforce_t1":true,"instruments":[{"symbol":"AAA","price_precision":2,"buy_lot":100}],"required_capabilities":["session_ledger"],"sessions":[
    {"session_date":"2025-01-02","open_ts_ns":t,"valuation_ts_ns":t+1000000000,"quotes":[quote(t,"10"),quote(t+1000000000,"11")],"orders":[{"id":"buy","symbol":"AAA","information_ts_ns":t-1,"side":"buy","quantity":"100"},{"id":"same-day-sell","symbol":"AAA","information_ts_ns":t,"side":"sell","quantity":"100"}]},
    {"session_date":"2025-01-03","open_ts_ns":t+86400000000000,"valuation_ts_ns":t+86401000000000,"quotes":[quote(t+86400000000000,"12"),quote(t+86401000000000,"12")],"orders":[{"id":"next-day-sell","symbol":"AAA","information_ts_ns":t+1000000000,"side":"sell","quantity":"100"}]}
    ]})
}
fn req(v: Value) -> SessionRequest {
    serde_json::from_value(v).unwrap()
}
#[test]
fn daily_balances_come_from_streaming_account_and_t1_denials() {
    let a = run_sessions(&req(fixture())).unwrap();
    assert_eq!(a.final_cash, "10197.8");
    assert_eq!(a.final_nav, "10197.8");
    assert_eq!(a.total_commission, "2.2");
    assert_eq!(a.daily_ledger.len(), 2);
    assert_eq!(a.daily_ledger[0].cash, "8999");
    assert_eq!(a.daily_ledger[0].nav, "10099");
    assert_eq!(a.daily_positions[0].quantity, "100");
    assert_eq!(a.orders[1].status, "DENIED");
    assert_eq!(a.fills.len(), 2);
}
#[test]
fn zero_trade_sessions_still_have_complete_snapshots() {
    let mut v = fixture();
    for s in v["sessions"].as_array_mut().unwrap() {
        s["orders"] = json!([]);
    }
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.daily_ledger.len(), 2);
    assert!(a.daily_positions.is_empty());
    assert_eq!(a.final_nav, "10000");
}
#[test]
fn competing_sells_cannot_reuse_t1_eligibility() {
    let mut v = fixture();
    let mut o = v["sessions"][1]["orders"][0].clone();
    o["id"] = json!("competing-sell");
    v["sessions"][1]["orders"].as_array_mut().unwrap().push(o);
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.orders.last().unwrap().status, "DENIED");
    assert_eq!(a.fills.len(), 2);
}
#[test]
fn configured_lots_and_side_limits_use_denial_events() {
    let mut v = fixture();
    v["sessions"][0]["orders"][0]["quantity"] = json!("137");
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.orders[0].status, "DENIED");
    assert!(a.fills.is_empty());
    let mut v = fixture();
    v["sessions"][0]["quotes"][0]["limit_up"] = json!(true);
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.orders[0].status, "DENIED");
    assert!(a.fills.is_empty());
}
#[test]
fn quote_liquidity_is_shared_and_ioc_does_not_invent_capacity() {
    let mut v = fixture();
    v["fee_bps"] = json!("0");
    v["sessions"].as_array_mut().unwrap().truncate(1);
    v["sessions"][0]["orders"]
        .as_array_mut()
        .unwrap()
        .truncate(1);
    v["sessions"][0]["orders"][0]["quantity"] = json!("200");
    v["sessions"][0]["quotes"][0]["ask_size"] = json!("100");
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(
        a.fills
            .iter()
            .map(|f| f.quantity.parse::<u64>().unwrap())
            .sum::<u64>(),
        100
    );
    assert_eq!(a.daily_ledger[0].cash, "9000");
}
#[test]
fn rejects_missing_or_stale_session_valuation_and_adjusted_prices() {
    let mut v = fixture();
    v["price_basis"] = json!("adjusted");
    assert!(run_sessions(&req(v)).is_err());
    let mut v = fixture();
    v["sessions"][0]["valuation_ts_ns"] = json!(1735781402000000000_u64);
    assert!(run_sessions(&req(v)).is_err());
    let mut v = fixture();
    v["sessions"][1]["session_date"] = json!("2025-01-02");
    assert!(run_sessions(&req(v)).is_err());
}

#[test]
fn disabling_t1_is_visible_and_allows_same_day_sale() {
    let mut v = fixture();
    v["enforce_t1"] = json!(false);
    let a = run_sessions(&req(v)).unwrap();
    assert!(!a.enforce_t1);
    assert_eq!(a.final_cash, "10097.9");
    assert_eq!(a.orders[1].status, "FILLED");
    assert_eq!(a.orders[2].status, "DENIED");
}
#[test]
fn zero_ask_liquidity_and_suspension_do_not_fill() {
    for field in ["ask_size", "tradable"] {
        let mut v = fixture();
        v["sessions"][0]["quotes"][0][field] = if field == "tradable" {
            json!(false)
        } else {
            json!("0")
        };
        let a = run_sessions(&req(v)).unwrap();
        assert!(a.fills.is_empty());
        assert_eq!(a.final_cash, "10000");
    }
}
#[test]
fn shared_quote_capacity_cannot_fill_competing_buys() {
    let mut v = fixture();
    v["sessions"].as_array_mut().unwrap().truncate(1);
    v["sessions"][0]["orders"]
        .as_array_mut()
        .unwrap()
        .truncate(1);
    v["sessions"][0]["quotes"][0]["ask_size"] = json!("100");
    let mut second = v["sessions"][0]["orders"][0].clone();
    second["id"] = json!("second-buy");
    v["sessions"][0]["orders"]
        .as_array_mut()
        .unwrap()
        .push(second);
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(
        a.fills
            .iter()
            .map(|f| f.quantity.parse::<u64>().unwrap())
            .sum::<u64>(),
        100
    );
}
#[test]
fn session_execution_is_reproducible() {
    let r = req(fixture());
    assert_eq!(run_sessions(&r).unwrap(), run_sessions(&r).unwrap());
}

#[test]
fn unsupported_corporate_actions_are_never_ignored() {
    let mut v = fixture();
    v["corporate_actions"] = json!([]);
    assert!(serde_json::from_value::<SessionRequest>(v).is_err());
    let mut v = fixture();
    v["required_capabilities"] = json!(["corporate_actions"]);
    assert!(run_sessions(&req(v)).is_err());
}

#[test]
fn blocked_orders_explain_their_actual_upstream_denial_event() {
    let a = run_sessions(&req(fixture())).unwrap();
    assert!(a.rejections.iter().any(|r| r.order_id == "same-day-sell"
        && r.reason == "SELLABLE_QUANTITY"
        && r.event_type == "denied"));
    assert_eq!(a.initial_cash, "10000");
}

#[test]
fn partial_sell_cancellation_releases_t1_reservation_for_a_retry() {
    let mut v = fixture();
    v["sessions"][1]["quotes"][0]["bid_size"] = json!("50");
    let mut retry = v["sessions"][1]["orders"][0].clone();
    retry["id"] = json!("retry-sell");
    retry["quantity"] = json!("50");
    retry["information_ts_ns"] = v["sessions"][1]["open_ts_ns"].clone();
    v["sessions"][1]["orders"]
        .as_array_mut()
        .unwrap()
        .push(retry);
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.orders[2].status, "CANCELED");
    assert_eq!(a.orders[2].filled_quantity, "50");
    assert_eq!(a.orders[3].status, "FILLED");
    assert_eq!(a.final_cash, "10197.8");
    assert_eq!(a.total_commission, "2.2");
}
#[test]
fn displayed_liquidity_retains_consumption_until_size_changes() {
    for (next_size, expected) in [("100", 100_u64), ("200", 200_u64)] {
        let mut v = fixture();
        v["sessions"].as_array_mut().unwrap().truncate(1);
        v["sessions"][0]["orders"]
            .as_array_mut()
            .unwrap()
            .truncate(1);
        v["sessions"][0]["quotes"][0]["ask_size"] = json!("100");
        v["sessions"][0]["quotes"][1]["ask_size"] = json!(next_size);
        v["sessions"][0]["quotes"][1]["bid"] = json!("10");
        v["sessions"][0]["quotes"][1]["ask"] = json!("10");
        let mut next = v["sessions"][0]["orders"][0].clone();
        next["id"] = json!("second");
        next["information_ts_ns"] = v["sessions"][0]["open_ts_ns"].clone();
        v["sessions"][0]["orders"]
            .as_array_mut()
            .unwrap()
            .push(next);
        let a = run_sessions(&req(v)).unwrap();
        assert_eq!(
            a.fills
                .iter()
                .map(|f| f.quantity.parse::<u64>().unwrap())
                .sum::<u64>(),
            expected
        );
    }
}
