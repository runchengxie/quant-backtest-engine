use quant_backtest_engine::lot_planning::{LotRequest, plan_lots};
use serde_json::json;
fn input() -> LotRequest {
    serde_json::from_value(json!({"schema_version":"engine_lot_request.v1","prices":["6","4"],"target_quantities":["1.5","1.5"],"max_lots":[3,3],"lot_sizes":[1,1],"cash_budget":"14","minimum_commission":"1","proportional_commission":"0","max_states":100000,"candidate_quantities":[0,2]})).unwrap()
}
#[test]
fn exact_minimum_fee_oracle_and_candidate_gap() {
    let r = plan_lots(&input()).unwrap();
    assert_eq!(r.status, "optimal_exhaustive");
    assert_eq!(r.quantities, Some(vec![1, 1]));
    assert_eq!(r.spent.as_deref(), Some("12"));
    assert_eq!(r.objective.as_deref(), Some("0.5"));
    assert_eq!(r.candidate_gap.as_deref(), Some("2"));
    assert_eq!(r.evaluated, 16);
}
#[test]
fn exact_budget_and_lexicographic_ties() {
    let mut q = input();
    q.prices = vec!["0.1".into(), "0.2".into()];
    q.target_quantities = vec!["1".into(), "1".into()];
    q.cash_budget = "0.3".into();
    q.minimum_commission = "0".into();
    q.candidate_quantities = None;
    let r = plan_lots(&q).unwrap();
    assert_eq!(r.quantities, Some(vec![1, 1]));
    assert_eq!(r.spent.as_deref(), Some("0.3"));
    q.prices = vec!["1".into(), "1".into()];
    q.target_quantities = vec!["0.5".into(), "0.5".into()];
    q.cash_budget = "10".into();
    assert_eq!(plan_lots(&q).unwrap().quantities, Some(vec![0, 0]));
}
#[test]
fn bounds_reject_and_search_limit_never_claims_optimality() {
    let mut q = input();
    q.max_states = 1;
    let r = plan_lots(&q).unwrap();
    assert_eq!(r.status, "search_limit");
    assert!(r.quantities.is_none());
    assert_eq!(r.evaluated, 0);
    q.max_states = 0;
    assert!(plan_lots(&q).is_err());
    q.max_states = 100000;
    q.prices[0] = "0.00001".into();
    assert!(plan_lots(&q).is_err());
    q.prices[0] = "NaN".into();
    assert!(plan_lots(&q).is_err());
}

#[test]
fn maximal_precision_and_overflowing_domain_are_explicit() {
    let mut q = input();
    q.prices = vec!["1".into(); 16];
    q.target_quantities = vec!["999999999.9999".into(); 16];
    q.max_lots = vec![0; 16];
    q.lot_sizes = vec![1; 16];
    q.candidate_quantities = None;
    let r = plan_lots(&q).unwrap();
    assert_eq!(r.evaluated, 1);
    assert_eq!(
        r.objective.as_deref(),
        Some("15999999999996800000.00000016")
    );
    q.max_lots = vec![1000000000; 16];
    let r = plan_lots(&q).unwrap();
    assert_eq!(r.status, "search_limit");
    assert_eq!(r.domain_states, None);
}
