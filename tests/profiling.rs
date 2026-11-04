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
    assert!(phases.strategy_quote_callbacks > 0);
    assert!(phases.strategy_pending_checks > 0);
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

#[test]
fn idle_quotes_do_not_clone_live_account_history() {
    let mut request: SessionRequest =
        serde_json::from_str(include_str!("../fixtures/sessions.json")).unwrap();
    for session in &mut request.sessions {
        session.orders.clear();
    }
    let (result, phases) = run_sessions_profiled(&request).unwrap();
    assert!(result.orders.is_empty());
    assert_eq!(phases.strategy_cache_reads, 0);
    assert!(phases.strategy_quote_callbacks > 0);
}

#[test]
fn future_information_and_other_symbols_do_not_read_accounts() {
    let mut request: SessionRequest =
        serde_json::from_str(include_str!("../fixtures/sessions.json")).unwrap();
    request.sessions.truncate(1);
    request.sessions[0].orders.truncate(1);
    let last_ts = request.sessions[0].quotes.last().unwrap().ts_ns;
    request.sessions[0].orders[0].information_ts_ns = last_ts - 1;
    let mut other = request.instruments[0].clone();
    other.symbol = "BBB".into();
    request.instruments.push(other);
    let mut quotes = Vec::new();
    for quote in &request.sessions[0].quotes {
        quotes.push(quote.clone());
        let mut other = quote.clone();
        other.symbol = "BBB".into();
        quotes.push(other);
    }
    request.sessions[0].quotes = quotes;
    let (result, phases) = run_sessions_profiled(&request).unwrap();
    assert_eq!(phases.strategy_quote_callbacks, 4);
    assert_eq!(phases.strategy_cache_reads, 1);
    assert_eq!(result.fills.len(), 1);
    assert_eq!(result.fills[0].ts_ns, last_ts);
}

#[test]
fn pending_checks_exclude_future_sessions_and_other_instruments() {
    let mut request: SessionRequest =
        serde_json::from_str(include_str!("../fixtures/sessions.json")).unwrap();
    // All intents remain pending: an information timestamp equal to valuation
    // cannot be consumed. Only the matching session/symbol bucket needs checks.
    for session in &mut request.sessions {
        for order in &mut session.orders {
            order.information_ts_ns = session.valuation_ts_ns;
        }
    }
    let mut other = request.instruments[0].clone();
    other.symbol = "BBB".into();
    request.instruments.push(other);
    for session in &mut request.sessions {
        let mut quotes = Vec::new();
        for quote in &session.quotes {
            quotes.push(quote.clone());
            let mut other = quote.clone();
            other.symbol = "BBB".into();
            quotes.push(other);
        }
        session.quotes = quotes;
    }
    for n in 0..100 {
        let mut order = request.sessions[1].orders[0].clone();
        order.id = format!("future-{n}");
        request.sessions[1].orders.push(order);
    }
    let (result, phases) = run_sessions_profiled(&request).unwrap();
    assert_eq!(phases.strategy_quote_callbacks, 8);
    assert_eq!(phases.strategy_cache_reads, 0);
    // Two first-session intents and 101 second-session intents, each checked
    // on two AAA quotes. The four BBB callbacks inspect zero pending intents.
    assert_eq!(phases.strategy_pending_checks, 206);
    assert!(result.fills.is_empty());
    assert_eq!(result.final_cash, "10000");
    assert_eq!(result.final_nav, "10000");
}
