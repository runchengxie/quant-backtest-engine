//! Session boundaries drive upstream streaming and cache-derived ledger snapshots.
use crate::{
    Request,
    contract::{Instrument, decimal},
    nautilus::{create_engine, snapshot},
    session_contract::{
        DailyBalance, DailyPosition, MarketSession, SESSION_CAPABILITIES, SessionConfig,
        SessionReport, SessionRequest, SessionResult, SessionValidation,
    },
    session_strategy::{SessionState, SessionStrategy},
};
use anyhow::{Result, ensure};
use nautilus_model::{
    data::{Data, QuoteTick},
    events::OrderEventAny,
    identifiers::ClientOrderId,
    identifiers::InstrumentId,
    orders::Order,
    types::{Currency, Price, Quantity},
};
use rust_decimal::Decimal;
use std::{cell::RefCell, collections::BTreeMap, rc::Rc, time::Instant};

pub(crate) fn execute(request: &SessionRequest) -> Result<SessionResult> {
    execute_measured(
        &SessionConfig::from(request),
        request.sessions.iter().cloned().map(Ok),
        false,
        |_| Ok(()),
    )
    .map(|(result, _)| result)
}

#[derive(Default, serde::Serialize)]
pub struct SessionTimings {
    pub validation_clone_seconds: f64,
    pub setup_seconds: f64,
    pub quote_conversion_load_seconds: f64,
    pub replay_matching_accounting_seconds: f64,
    pub snapshot_ledger_seconds: f64,
    pub finalization_seconds: f64,
    pub strategy_quote_callbacks: u64,
    pub strategy_pending_checks: u64,
    pub strategy_cache_reads: u64,
    pub strategy_rules_seconds: f64,
    pub strategy_cache_seconds: f64,
    pub strategy_instrument_seconds: f64,
    pub strategy_pending_seconds: f64,
}

pub(crate) fn execute_profiled(
    request: &SessionRequest,
) -> Result<(SessionResult, SessionTimings)> {
    execute_measured(
        &SessionConfig::from(request),
        request.sessions.iter().cloned().map(Ok),
        true,
        |_| Ok(()),
    )
}

pub(crate) fn execute_iter<I>(config: SessionConfig, sessions: I) -> Result<SessionResult>
where
    I: Iterator<Item = Result<MarketSession>>,
{
    execute_measured(&config, sessions, false, |_| Ok(())).map(|(result, _)| result)
}

pub(crate) fn execute_iter_with_reports<I, F>(
    config: SessionConfig,
    sessions: I,
    report: F,
) -> Result<SessionResult>
where
    I: Iterator<Item = Result<MarketSession>>,
    F: FnMut(SessionReport) -> Result<()>,
{
    execute_measured(&config, sessions, false, report).map(|(result, _)| result)
}

fn execute_measured(
    request: &SessionConfig,
    sessions: impl Iterator<Item = Result<MarketSession>>,
    profile: bool,
    mut report: impl FnMut(SessionReport) -> Result<()>,
) -> Result<(SessionResult, SessionTimings)> {
    let mut validation = SessionValidation::new(request)?;
    let mut timings = SessionTimings::default();
    let started = profile.then(Instant::now);
    let currency = if request.currency == "CNY" {
        Currency::CNY()
    } else {
        Currency::USD()
    };
    let mut base = Request {
        schema_version: "engine_request.v1".into(),
        initial_cash: request.initial_cash.clone(),
        fee_bps: request.fee_bps.clone(),
        instruments: request
            .instruments
            .iter()
            .map(|i| Instrument {
                symbol: i.symbol.clone(),
                price_precision: i.price_precision,
            })
            .collect(),
        quotes: Vec::new(),
        orders: Vec::new(),
        required_capabilities: Vec::new(),
    };
    let mut engine = create_engine(&base, currency, true)?;
    let state = Rc::new(RefCell::new(SessionState::default()));
    state.borrow_mut().profile = profile;
    engine
        .0
        .add_strategy(SessionStrategy::new(request, state.clone(), currency)?)?;
    let precisions = request
        .instruments
        .iter()
        .map(|i| (i.symbol.as_str(), i.price_precision))
        .collect::<BTreeMap<_, _>>();
    let mut daily_ledger = Vec::new();
    let mut daily_positions = Vec::new();
    let mut latest = None;
    let mut prior_commission = Decimal::ZERO;
    timings.setup_seconds = started.map_or(0.0, |t| t.elapsed().as_secs_f64());
    let mut final_marks = BTreeMap::new();
    for session in sessions {
        let session = session?;
        validation.validate(&session)?;
        let started = profile.then(Instant::now);
        {
            let mut state = state.borrow_mut();
            ensure!(
                state.reservations.values().all(|(_, q)| q.is_zero()),
                "IOC reservations remain at session boundary"
            );
            state.load(&session)?;
            state.reservations.clear();
        }
        let mut data = Vec::new();
        let mut marks = BTreeMap::new();
        for q in &session.quotes {
            let bid = decimal(&q.bid)?;
            let ask = decimal(&q.ask)?;
            marks.insert(q.symbol.as_str(), (bid + ask) / Decimal::from(2));
            data.push(Data::Quote(QuoteTick::new(
                InstrumentId::from(format!("{}.SIM", q.symbol)),
                Price::from_decimal_dp(bid, precisions[q.symbol.as_str()])?,
                Price::from_decimal_dp(ask, precisions[q.symbol.as_str()])?,
                Quantity::from_decimal_dp(decimal(&q.bid_size)?, 0)?,
                Quantity::from_decimal_dp(decimal(&q.ask_size)?, 0)?,
                q.ts_ns.into(),
                q.ts_ns.into(),
            )));
        }
        engine.0.add_data(data, None, true, true)?;
        timings.quote_conversion_load_seconds += started.map_or(0.0, |t| t.elapsed().as_secs_f64());
        let started = profile.then(Instant::now);
        let before = engine.0.iteration();
        engine.0.run(None, None, None, true)?;
        ensure!(
            engine.0.iteration() - before == session.quotes.len(),
            "session replay ended before valuation"
        );
        timings.replay_matching_accounting_seconds +=
            started.map_or(0.0, |t| t.elapsed().as_secs_f64());
        let started = profile.then(Instant::now);
        let session_ids = session
            .orders
            .iter()
            .map(|o| o.id.clone())
            .collect::<std::collections::BTreeSet<_>>();
        base.orders.extend(session.orders);
        let result = snapshot(&engine, &base.orders, &marks, currency)?;
        daily_ledger.push(DailyBalance {
            session_date: session.session_date.clone(),
            valuation_ts_ns: session.valuation_ts_ns,
            cash: result.cash.clone(),
            positions_value: result.positions_value.clone(),
            nav: result.equity.clone(),
            commission: (decimal(&result.commission)? - prior_commission)
                .normalize()
                .to_string(),
        });
        prior_commission = decimal(&result.commission)?;
        let position_start = daily_positions.len();
        state.borrow_mut().sellable.clear();
        for p in &result.positions {
            state.borrow_mut().sellable.insert(
                InstrumentId::from(format!("{}.SIM", p.symbol)),
                decimal(&p.quantity)?,
            );
            daily_positions.push(DailyPosition {
                session_date: session.session_date.clone(),
                symbol: p.symbol.clone(),
                quantity: p.quantity.clone(),
                mark_price: p.mark_price.clone(),
                market_value: p.market_value.clone(),
            });
        }
        let rejections = rejections_for(
            &engine,
            base.orders.iter().filter(|o| session_ids.contains(&o.id)),
        );
        report(SessionReport {
            session_index: daily_ledger.len() - 1,
            session_date: session.session_date.clone(),
            valuation_ts_ns: session.valuation_ts_ns,
            balance: daily_ledger.last().unwrap().clone(),
            positions: daily_positions[position_start..].to_vec(),
            orders: result
                .orders
                .iter()
                .filter(|o| session_ids.contains(&o.id))
                .cloned()
                .collect(),
            fills: result
                .fills
                .iter()
                .filter(|f| session_ids.contains(&f.order_id))
                .cloned()
                .collect(),
            rejections,
        })?;
        latest = Some(result);
        engine.0.clear_data();
        state.borrow_mut().clear_input();
        final_marks = marks
            .into_iter()
            .map(|(symbol, mark)| (symbol.to_owned(), mark))
            .collect();
        timings.snapshot_ledger_seconds += started.map_or(0.0, |t| t.elapsed().as_secs_f64());
    }
    let started = profile.then(Instant::now);
    let prior = latest.ok_or_else(|| anyhow::anyhow!("sessions and instruments are required"))?;
    engine.0.end()?;
    let final_marks = final_marks
        .iter()
        .map(|(symbol, mark)| (symbol.as_str(), *mark))
        .collect();
    let last = snapshot(&engine, &base.orders, &final_marks, currency)?;
    ensure!(
        last.cash == prior.cash
            && last.equity == prior.equity
            && last.positions == prior.positions
            && last.commission == prior.commission,
        "upstream finalization changed the completed session ledger"
    );
    let rejections = rejections_for(&engine, base.orders.iter());
    let result = SessionResult {
        initial_cash: request.initial_cash.clone(),
        rejections,
        enforce_t1: request.enforce_t1,
        price_basis: request.price_basis.clone(),
        valuation_timezone: if request.currency == "CNY" {
            "Asia/Shanghai"
        } else {
            "UTC"
        }
        .into(),
        schema_version: "engine_result.v2".into(),
        backend: "nautilus".into(),
        backend_version: "0.66.0".into(),
        currency: request.currency.clone(),
        capabilities: SESSION_CAPABILITIES.iter().map(|s| (*s).into()).collect(),
        final_cash: last.cash,
        final_nav: last.equity,
        total_commission: last.commission,
        orders: last.orders,
        fills: last.fills,
        daily_ledger,
        daily_positions,
    };
    timings.finalization_seconds = started.map_or(0.0, |t| t.elapsed().as_secs_f64());
    let state = state.borrow();
    timings.strategy_quote_callbacks = state.quote_callbacks;
    timings.strategy_pending_checks = state.pending_checks;
    timings.strategy_cache_reads = state.cache_reads;
    timings.strategy_rules_seconds = state.rule_seconds;
    timings.strategy_cache_seconds = state.cache_seconds;
    timings.strategy_instrument_seconds = state.instrument_seconds;
    timings.strategy_pending_seconds = state.pending_seconds;
    Ok((result, timings))
}

fn rejections_for<'a>(
    engine: &crate::nautilus::Engine,
    intents: impl Iterator<Item = &'a crate::contract::OrderIntent>,
) -> Vec<crate::session_contract::Rejection> {
    let cache = engine.0.kernel().cache.borrow();
    let mut rejections = Vec::new();
    for intent in intents {
        if let Some(order) = cache.order(&ClientOrderId::from(intent.id.as_str())) {
            for event in order.events() {
                let rejected = match event {
                    OrderEventAny::Denied(e) => Some(("denied", e.reason.to_string())),
                    OrderEventAny::Rejected(e) => Some(("rejected", e.reason.to_string())),
                    _ => None,
                };
                if let Some((kind, reason)) = rejected {
                    rejections.push(crate::session_contract::Rejection {
                        order_id: intent.id.clone(),
                        reason,
                        event_type: kind.into(),
                    });
                }
            }
        }
    }
    rejections
}
