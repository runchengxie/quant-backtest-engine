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

#[test]
fn one_nanosecond_information_boundary_is_strict() {
    for delay in [0_u64, 1] {
        let mut v = fixture();
        v["sessions"].as_array_mut().unwrap().truncate(1);
        v["sessions"][0]["orders"]
            .as_array_mut()
            .unwrap()
            .truncate(1);
        let t = v["sessions"][0]["open_ts_ns"].as_u64().unwrap();
        v["sessions"][0]["orders"][0]["information_ts_ns"] = json!(t);
        v["sessions"][0]["quotes"][1]["ts_ns"] = json!(t + delay + 1);
        v["sessions"][0]["valuation_ts_ns"] = json!(t + delay + 1);
        let a = run_sessions(&req(v)).unwrap();
        assert_eq!(a.fills.len(), 1);
        assert_eq!(a.fills[0].ts_ns, t + delay + 1);
        assert_eq!(a.fills[0].price, "11");
    }
}

#[test]
fn unfilled_sale_cannot_finance_same_callback_purchase() {
    let mut v = fixture();
    v["initial_cash"] = json!("1001");
    v["sessions"][1]["quotes"][0]["bid_size"] = json!("0");
    let mut buy = v["sessions"][1]["orders"][0].clone();
    buy["id"] = json!("unfunded-buy");
    buy["side"] = json!("buy");
    v["sessions"][1]["orders"].as_array_mut().unwrap().push(buy);
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.orders.last().unwrap().status, "DENIED");
    assert_eq!(a.final_cash, "0");
    assert_eq!(a.fills.len(), 1);
    assert_eq!(a.daily_positions.last().unwrap().quantity, "100");
}

#[test]
fn pending_bucket_preserves_request_priority_across_information_times() {
    let mut v = fixture();
    v["sessions"].as_array_mut().unwrap().truncate(1);
    v["initial_cash"] = json!("1001");
    let t = v["sessions"][0]["open_ts_ns"].as_u64().unwrap();
    let mut first = v["sessions"][0]["orders"][0].clone();
    first["id"] = json!("first-later-information");
    first["information_ts_ns"] = json!(t + 1);
    let mut second = first.clone();
    second["id"] = json!("second-earlier-information");
    second["information_ts_ns"] = json!(t);
    v["sessions"][0]["orders"] = json!([first, second]);
    // Both remain pending on the first quote; both qualify on the next one.
    // Request order, not information-time sorting, determines who gets cash.
    v["sessions"][0]["quotes"][1]["bid"] = json!("10");
    v["sessions"][0]["quotes"][1]["ask"] = json!("10");
    v["sessions"][0]["quotes"][1]["ask_size"] = json!("100");
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.fills.len(), 1);
    assert_eq!(a.fills[0].order_id, "first-later-information");
    assert_eq!(a.fills[0].ts_ns, t + 1_000_000_000);
    assert_eq!(a.orders[1].status, "DENIED");
    assert_eq!(a.rejections[0].reason, "INSUFFICIENT_CASH_INCLUDING_FEES");
    assert_eq!(a.final_cash, "0");
    assert_eq!(a.final_nav, "1000");
    assert_eq!(a.total_commission, "1");
}

#[test]
fn deferred_intent_does_not_block_a_later_ready_intent() {
    let mut v = fixture();
    v["sessions"].as_array_mut().unwrap().truncate(1);
    v["initial_cash"] = json!("1001");
    let t = v["sessions"][0]["open_ts_ns"].as_u64().unwrap();
    let mut deferred = v["sessions"][0]["orders"][0].clone();
    deferred["id"] = json!("deferred");
    deferred["information_ts_ns"] = json!(t);
    let mut ready = deferred.clone();
    ready["id"] = json!("ready");
    ready["information_ts_ns"] = json!(t - 1);
    v["sessions"][0]["orders"] = json!([deferred, ready]);
    let a = run_sessions(&req(v)).unwrap();
    assert_eq!(a.fills.len(), 1);
    assert_eq!(a.fills[0].order_id, "ready");
    assert_eq!(a.fills[0].ts_ns, t);
    assert_eq!(a.orders[0].status, "DENIED");
    assert_eq!(a.final_cash, "0");
    assert_eq!(a.final_nav, "1100");
    assert_eq!(a.total_commission, "1");
}

#[test]
fn generated_partial_fills_conserve_cash_inventory_and_commission() {
    use quant_backtest_engine::contract::Side;
    use rust_decimal::Decimal;
    use std::str::FromStr;
    let d = |s: &str| Decimal::from_str(s).unwrap();
    for capacity in [0, 1, 49, 50, 99, 100, 101, 199, 200] {
        let mut v = fixture();
        v["sessions"][0]["orders"]
            .as_array_mut()
            .unwrap()
            .truncate(1);
        v["sessions"][0]["orders"][0]["quantity"] = json!("200");
        v["sessions"][0]["quotes"][0]["ask_size"] = json!(capacity.to_string());
        v["sessions"][1]["quotes"][0]["bid_size"] = json!((capacity / 2).to_string());
        v["sessions"][1]["orders"][0]["quantity"] = json!(capacity.to_string());
        if capacity == 0 {
            v["sessions"][1]["orders"] = json!([]);
        }
        let a = run_sessions(&req(v)).unwrap();
        let mut cash = Decimal::from(10000);
        let mut inventory = Decimal::ZERO;
        let mut fees = Decimal::ZERO;
        for f in &a.fills {
            let qty = d(&f.quantity);
            let gross = qty * d(&f.price);
            let sign = if f.side == Side::Buy {
                Decimal::ONE
            } else {
                -Decimal::ONE
            };
            inventory += sign * qty;
            cash -= sign * gross + d(&f.commission);
            fees += d(&f.commission);
        }
        assert_eq!(cash, d(&a.final_cash), "capacity {capacity}");
        assert_eq!(fees, d(&a.total_commission));
        let positions: Decimal = a
            .daily_positions
            .iter()
            .filter(|p| p.session_date == "2025-01-03")
            .map(|p| d(&p.quantity))
            .sum();
        assert_eq!(inventory, positions);
        assert_eq!(d(&a.final_nav), cash + inventory * Decimal::from(12));
        assert!(cash >= Decimal::ZERO);
        let bought: Decimal = a
            .fills
            .iter()
            .filter(|f| f.side == Side::Buy)
            .map(|f| d(&f.quantity))
            .sum();
        assert_eq!(bought, Decimal::from(capacity));
    }
}
