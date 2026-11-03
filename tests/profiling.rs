use quant_backtest_engine::{
    run_sessions, run_sessions_profiled, session_contract::SessionRequest,
};
#[test]
fn measurements_preserve_result_and_reject_invalid_requests() {
    let mut request: SessionRequest =
        serde_json::from_str(include_str!("../fixtures/sessions.json")).unwrap();
    let expected = run_sessions(&request).unwrap();
    let (actual, phases) = run_sessions_profiled(&request).unwrap();
    assert_eq!(actual, expected);
    let values = serde_json::to_value(phases).unwrap();
    assert!(
        values
            .as_object()
            .unwrap()
            .values()
            .all(|v| v.as_f64().unwrap().is_finite() && v.as_f64().unwrap() >= 0.0)
    );
    request.sessions.clear();
    assert!(run_sessions_profiled(&request).is_err());
}
