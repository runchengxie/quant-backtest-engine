//! Session boundaries drive upstream streaming and cache-derived ledger snapshots.
use crate::{
    Request,
    contract::{Instrument, decimal},
    nautilus::{create_engine, snapshot},
    session_contract::{
        DailyBalance, DailyPosition, SESSION_CAPABILITIES, SessionRequest, SessionResult,
    },
    session_strategy::{SessionState, SessionStrategy},
};
use anyhow::{Result, ensure};
use nautilus_model::{
    data::{Data, QuoteTick},
    identifiers::InstrumentId,
    types::{Currency, Price, Quantity},
};
use rust_decimal::Decimal;
use std::{cell::RefCell, collections::BTreeMap, rc::Rc};

pub(crate) fn execute(request: &SessionRequest) -> Result<SessionResult> {
    let currency = if request.currency == "CNY" {
        Currency::CNY()
    } else {
        Currency::USD()
    };
    let base = Request {
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
        orders: request
            .sessions
            .iter()
            .flat_map(|s| s.orders.clone())
            .collect(),
        required_capabilities: Vec::new(),
    };
    let mut engine = create_engine(&base, currency, true)?;
    let state = Rc::new(RefCell::new(SessionState::default()));
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
    for (index, session) in request.sessions.iter().enumerate() {
        {
            let mut state = state.borrow_mut();
            ensure!(
                state.reservations.values().all(|(_, q)| q.is_zero()),
                "IOC reservations remain at session boundary"
            );
            state.current = index;
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
        let before = engine.0.iteration();
        engine.0.run(None, None, None, true)?;
        ensure!(
            engine.0.iteration() - before == session.quotes.len(),
            "session replay ended before valuation"
        );
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
        latest = Some(result);
        engine.0.clear_data();
    }
    engine.0.end()?;
    let prior = latest.expect("validated sessions are nonempty");
    let final_session = request
        .sessions
        .last()
        .expect("validated sessions are nonempty");
    let mut final_marks = BTreeMap::new();
    for q in &final_session.quotes {
        final_marks.insert(
            q.symbol.as_str(),
            (decimal(&q.bid)? + decimal(&q.ask)?) / Decimal::from(2),
        );
    }
    let last = snapshot(&engine, &base.orders, &final_marks, currency)?;
    ensure!(
        last.cash == prior.cash
            && last.equity == prior.equity
            && last.positions == prior.positions
            && last.commission == prior.commission,
        "upstream finalization changed the completed session ledger"
    );
    Ok(SessionResult {
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
    })
}
