use quant_backtest_engine::{depth_contract::DepthRequest, run_depth};
use serde_json::{Value, json};
const T: u64 = 1_735_689_600_000_000_000;
fn snapshot(seq: u64, dt: u64, asks: Value) -> Value {
    json!({"kind":"snapshot","ts_ns":T+dt,"available_ns":T+dt,"sequence":seq,"bids":[{"price":"9.90","quantity":"100"}],"asks":asks,"trade_id":null,"trade_price":null,"trade_quantity":null,"aggressor":null})
}
fn command(id: &str, seq: u64, action: &str, q: &str, price: &str) -> Value {
    json!({"id":id,"event_sequence":seq,"information_ts_ns":T-1,"action":action,"quantity":q,"limit_price":price,"cancel_id":null})
}
fn request(events: Vec<Value>, commands: Vec<Value>) -> DepthRequest {
    serde_json::from_value(json!({"schema_version":"engine_depth_request.v1","currency":"CNY","initial_cash":"10000","fee_bps":"10","instrument":{"symbol":"AAA","price_precision":2},"insert_latency_ns":0,"cancel_latency_ns":0,"end_ns":T+10000,"events":events,"commands":commands,"required_capabilities":["l2_depth_events","account_feedback_targets"]})).unwrap()
}
fn asks() -> Value {
    json!([{"price":"10.00","quantity":"2"},{"price":"10.10","quantity":"3"}])
}
#[test]
fn multilevel_fill_and_cash_are_upstream_owned() {
    let r = run_depth(&request(
        vec![snapshot(1, 100, asks())],
        vec![command("buy", 1, "buy", "5", "10.10")],
    ))
    .unwrap();
    assert_eq!(
        r.account
            .fills
            .iter()
            .map(|f| (&*f.price, &*f.quantity))
            .collect::<Vec<_>>(),
        vec![("10", "2"), ("10.1", "3")]
    );
    assert_eq!(r.account.cash, "9949.65");
    assert_eq!(r.account.commission, "0.05");
    assert_eq!(r.account.positions[0].quantity, "5");
}
#[test]
fn account_feedback_target_uses_actual_partial_holdings() {
    let events = vec![
        snapshot(1, 100, json!([{"price":"10","quantity":"2"}])),
        snapshot(2, 200, json!([{"price":"10.20","quantity":"10"}])),
        snapshot(3, 300, json!([{"price":"10","quantity":"10"}])),
    ];
    let mut q = request(
        events,
        vec![
            command("first", 1, "target", "5", "10"),
            command("next", 2, "target", "5", "10"),
        ],
    );
    // A resting first order must block a duplicate target order, not pre-fund or double-count it.
    let r = run_depth(&q).unwrap();
    assert_eq!(r.decisions.len(), 2);
    assert_eq!(r.decisions[1].held_quantity, "2");
    assert_eq!(r.decisions[1].outcome, "waiting_for_working_order");
    q.commands[1].action = quant_backtest_engine::depth_contract::DepthAction::Cancel;
    q.commands[1].quantity = "0".into();
    q.commands[1].limit_price = "0".into();
    q.commands[1].cancel_id = Some("first".into());
    q.commands
        .push(serde_json::from_value(command("third", 3, "target", "5", "10")).unwrap());
    let r = run_depth(&q).unwrap();
    assert!(
        r.account
            .orders
            .iter()
            .any(|o| o.id == "first" && o.status == "CANCELED")
    );
    assert_eq!(r.decisions[2].held_quantity, "2");
    assert_eq!(r.decisions[2].submitted_quantity, "3");
    assert_eq!(r.account.positions[0].quantity, "5");
}
#[test]
fn delayed_order_uses_later_depth_and_explicit_horizon() {
    let mut q = request(
        vec![
            snapshot(1, 100, asks()),
            snapshot(2, 150, json!([{"price":"11","quantity":"10"}])),
        ],
        vec![command("buy", 1, "buy", "5", "10.10")],
    );
    q.insert_latency_ns = 100;
    let r = run_depth(&q).unwrap();
    assert!(r.account.fills.is_empty());
    assert_eq!(r.account.cash, "10000");
}
#[test]
fn malformed_depth_is_rejected_without_silent_sorting() {
    let q = request(
        vec![snapshot(1, 200, asks()), snapshot(2, 100, asks())],
        vec![],
    );
    assert!(run_depth(&q).is_err());
    let mut q = request(
        vec![snapshot(1, 100, asks())],
        vec![command("bad", 1, "buy", "1", "10")],
    );
    q.commands[0].information_ts_ns = T + 100;
    assert!(run_depth(&q).is_err());
}
#[test]
fn observation_horizon_processes_latency_after_last_market_event() {
    let mut q = request(
        vec![snapshot(1, 100, asks())],
        vec![command("buy", 1, "buy", "5", "10.10")],
    );
    q.insert_latency_ns = 100;
    let r = run_depth(&q).unwrap();
    assert_eq!(r.account.positions[0].quantity, "5");
    assert!(r.account.fills.iter().all(|f| f.ts_ns == T + 200));
}
#[test]
fn explicit_trade_tick_can_fill_a_passive_order() {
    let trade = json!({"kind":"trade","ts_ns":T+200,"available_ns":T+200,"sequence":2,"bids":[],"asks":[],"trade_id":"print-1","trade_price":"9.95","trade_quantity":"2","aggressor":"sell"});
    let r = run_depth(&request(
        vec![snapshot(1, 100, asks()), trade],
        vec![command("passive", 1, "buy", "3", "9.95")],
    ))
    .unwrap();
    assert_eq!(r.account.positions[0].quantity, "2");
    assert_eq!(r.account.fills[0].price, "9.95");
}
#[test]
fn cancel_arrival_race_keeps_the_actual_trade() {
    let events = vec![
        snapshot(1, 100, asks()),
        snapshot(2, 150, asks()),
        json!({"kind":"trade","ts_ns":T+200,"available_ns":T+200,"sequence":3,"bids":[],"asks":[],"trade_id":"print-1","trade_price":"9.95","trade_quantity":"3","aggressor":"sell"}),
    ];
    let mut cancel = command("cancel", 2, "cancel", "0", "0");
    cancel["cancel_id"] = json!("passive");
    let mut q = request(
        events,
        vec![command("passive", 1, "buy", "3", "9.95"), cancel],
    );
    let timely = run_depth(&q).unwrap();
    assert!(timely.account.fills.is_empty());
    q.cancel_latency_ns = 100;
    let late = run_depth(&q).unwrap();
    assert_eq!(late.account.positions[0].quantity, "3");
    assert_eq!(late.account.orders[0].status, "FILLED");
}
#[test]
fn delta_events_replace_sizes_and_delete_explicit_levels() {
    let delta = json!({"kind":"delta","ts_ns":T+200,"available_ns":T+200,"sequence":2,"bids":[],"asks":[{"price":"10","quantity":"0"},{"price":"10.10","quantity":"4"}],"trade_id":null,"trade_price":null,"trade_quantity":null,"aggressor":null});
    let r = run_depth(&request(
        vec![snapshot(1, 100, asks()), delta],
        vec![command("buy", 2, "buy", "4", "10.10")],
    ))
    .unwrap();
    assert_eq!(r.account.fills.len(), 1);
    assert_eq!(r.account.fills[0].price, "10.1");
    assert_eq!(r.account.fills[0].quantity, "4");
}
#[test]
fn delayed_market_availability_requires_a_different_clock_profile() {
    let mut q = request(vec![snapshot(1, 100, asks())], vec![]);
    q.events[0].available_ns += 10;
    assert!(run_depth(&q).is_err());
}
#[test]
fn sparse_future_market_data_does_not_move_an_earlier_arrival() {
    for later in [250, 350, 600] {
        let mut q = request(
            vec![
                snapshot(1, 100, asks()),
                snapshot(2, later, json!([{"price":"11","quantity":"100"}])),
            ],
            vec![command("buy", 1, "buy", "5", "10.10")],
        );
        q.insert_latency_ns = 100;
        let r = run_depth(&q).unwrap();
        assert_eq!(r.account.positions[0].quantity, "5");
        assert!(r.account.fills.iter().all(|f| f.ts_ns == T + 200));
        assert_eq!(r.decisions.len(), 1);
    }
}
#[test]
fn positive_cancel_latency_arrives_between_market_observations() {
    let events = vec![
        snapshot(1, 100, asks()),
        snapshot(2, 150, asks()),
        json!({"kind":"trade","ts_ns":T+200,"available_ns":T+200,"sequence":3,"bids":[],"asks":[],"trade_id":"print-1","trade_price":"9.95","trade_quantity":"3","aggressor":"sell"}),
    ];
    let mut c = command("cancel", 2, "cancel", "0", "0");
    c["cancel_id"] = json!("passive");
    let mut q = request(events, vec![command("passive", 1, "buy", "3", "9.95"), c]);
    q.cancel_latency_ns = 10;
    let r = run_depth(&q).unwrap();
    assert!(r.account.fills.is_empty());
    assert!(
        r.receipts
            .iter()
            .any(|e| e.kind == "canceled" && e.ts_ns == T + 160)
    );
}
#[test]
fn currency_rounded_notional_can_use_the_exact_available_cash() {
    let mut q = request(
        vec![snapshot(1, 100, json!([{"price":"10.001","quantity":"1"}]))],
        vec![command("buy", 1, "buy", "1", "10.001")],
    );
    q.instrument.price_precision = 3;
    q.initial_cash = "10".into();
    q.fee_bps = "0".into();
    let r = run_depth(&q).unwrap();
    assert_eq!(r.account.cash, "0");
    assert_eq!(r.account.positions[0].quantity, "1");
}
#[test]
fn in_flight_buys_share_one_conservative_cash_budget() {
    let events = vec![
        snapshot(1, 100, json!([{"price":"10","quantity":"2000"}])),
        snapshot(2, 110, json!([{"price":"10","quantity":"2000"}])),
    ];
    let mut q = request(
        events,
        vec![
            command("first", 1, "buy", "600", "10"),
            command("second", 2, "buy", "600", "10"),
        ],
    );
    q.fee_bps = "0".into();
    q.insert_latency_ns = 100;
    let r = run_depth(&q).unwrap();
    assert_eq!(r.decisions[1].admissible_cash, "4000");
    assert_eq!(r.decisions[1].outcome, "denied_cash");
    assert_eq!(r.account.cash, "4000");
    assert_eq!(r.account.positions[0].quantity, "600");
}

#[test]
fn equal_clock_market_update_precedes_positive_latency_arrival() {
    let mut q = request(
        vec![
            snapshot(1, 100, asks()),
            snapshot(2, 200, json!([{"price":"11","quantity":"10"}])),
        ],
        vec![command("buy", 1, "buy", "5", "10.10")],
    );
    q.insert_latency_ns = 100;
    let r = run_depth(&q).unwrap();
    assert!(r.account.fills.is_empty());
    assert_eq!(r.decisions.len(), 1);
}

#[test]
fn equal_clock_events_keep_supplied_sequence_for_decisions() {
    let q = request(
        vec![
            snapshot(1, 100, asks()),
            snapshot(2, 100, json!([{"price":"11","quantity":"10"}])),
        ],
        vec![command("buy", 2, "buy", "5", "10.10")],
    );
    let r = run_depth(&q).unwrap();
    assert!(r.account.fills.is_empty());
    assert_eq!(r.decisions.len(), 1);
}
