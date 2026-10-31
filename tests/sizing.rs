use quant_backtest_engine::sizing::{SizingRequest, size_targets};
use serde_json::{Value, json};
fn fixture() -> Value {
    json!({"schema_version":"sizing_request.v1","currency":"CNY","information_ts_ns":1735689600000000000_u64,"cash":"1000","fee_bps":"10","assets":[{"symbol":"AAA","held_quantity":"0","reference_price":"10","price_ts_ns":1735689599999999999_u64,"target_weight":"0.5","buy_lot":1}]})
}
fn request(v: Value) -> SizingRequest {
    serde_json::from_value(v).unwrap()
}
#[test]
fn fractional_weight_plans_only_asof_quantities() {
    let result = size_targets(&request(fixture())).unwrap();
    assert_eq!(result.marked_equity, "1000");
    assert_eq!(result.projected_cash, "499.5");
    assert_eq!(result.orders[0].quantity, "50");
    assert_eq!(result.orders[0].information_ts_ns, 1735689600000000000);
}
#[test]
fn all_in_target_reserves_rounded_fees_and_reports_residual() {
    let mut v = fixture();
    v["assets"][0]["target_weight"] = json!("1");
    let a = size_targets(&request(v)).unwrap();
    assert_eq!(a.orders[0].quantity, "99");
    assert_eq!(a.projected_cash, "9.01");
    assert_eq!(a.targets[0].desired_quantity, "100");
    assert_eq!(a.targets[0].planned_quantity, "99");
}
#[test]
fn sells_precede_buys_and_sale_proceeds_are_projected() {
    let mut v = fixture();
    v["cash"] = json!("0");
    v["assets"][0]["held_quantity"] = json!("100");
    v["assets"][0]["target_weight"] = json!("0");
    v["assets"].as_array_mut().unwrap().push(json!({"symbol":"BBB","held_quantity":"0","reference_price":"10","price_ts_ns":1735689599999999999_u64,"target_weight":"1","buy_lot":1}));
    let a = size_targets(&request(v)).unwrap();
    assert_eq!(a.orders[0].symbol, "AAA");
    assert_eq!(a.orders[1].symbol, "BBB");
    assert_eq!(a.orders[1].quantity, "99");
    assert_eq!(a.projected_cash, "8.01");
}
#[test]
fn buy_lots_and_odd_lot_liquidations_are_explicit() {
    let mut v = fixture();
    v["fee_bps"] = json!("0");
    v["assets"][0]["buy_lot"] = json!(100);
    v["assets"][0]["target_weight"] = json!("1");
    let a = size_targets(&request(v.clone())).unwrap();
    assert_eq!(a.orders[0].quantity, "100");
    v["assets"][0]["held_quantity"] = json!("137");
    v["assets"][0]["target_weight"] = json!("0");
    let a = size_targets(&request(v)).unwrap();
    assert_eq!(a.orders[0].quantity, "137");
}
#[test]
fn sizing_is_stable_under_asset_input_reordering() {
    let mut v = fixture();
    v["assets"][0]["target_weight"] = json!("0.5");
    let mut b = v["assets"][0].clone();
    b["symbol"] = json!("BBB");
    v["assets"].as_array_mut().unwrap().push(b);
    let a = size_targets(&request(v.clone())).unwrap();
    v["assets"].as_array_mut().unwrap().reverse();
    assert_eq!(a, size_targets(&request(v)).unwrap());
}
#[test]
fn invalid_or_lookahead_plans_fail() {
    for (field, value) in [
        ("price_ts_ns", json!(1735689600000000001_u64)),
        ("buy_lot", json!(0)),
        ("target_weight", json!("1.1")),
        ("held_quantity", json!("1.5")),
        ("reference_price", json!("0")),
    ] {
        let mut v = fixture();
        v["assets"][0][field] = value;
        assert!(size_targets(&request(v)).is_err(), "{field}");
    }
    let mut v = fixture();
    let duplicate = v["assets"][0].clone();
    v["assets"].as_array_mut().unwrap().push(duplicate);
    assert!(size_targets(&request(v)).is_err());
}
