use crate::{
    Request,
    contract::decimal,
    depth_contract::{DEPTH_CAPABILITIES, DepthReceipt, DepthRequest, DepthResult},
    depth_strategy::{DepthState, DepthStrategy},
    nautilus::{create_engine_with_depth, snapshot},
};
use anyhow::{Result, ensure};
use nautilus_core::nanos::DurationNanos;
use nautilus_execution::models::latency::{LatencyModelHandle, StaticLatencyModel};
use nautilus_model::{
    data::{BookOrder, Data, OrderBookDelta, OrderBookDeltas, TradeTick},
    enums::{AggressorSide, BookAction, BookType, OrderSide, RecordFlag},
    identifiers::{InstrumentId, TradeId},
    types::{Currency, Price, Quantity},
};
use std::{cell::RefCell, collections::BTreeMap, rc::Rc};
pub(crate) fn execute(request: &DepthRequest) -> Result<DepthResult> {
    let currency = if request.currency == "CNY" {
        Currency::CNY()
    } else {
        Currency::USD()
    };
    let base = Request {
        schema_version: "engine_request.v1".into(),
        initial_cash: request.initial_cash.clone(),
        fee_bps: request.fee_bps.clone(),
        instruments: vec![request.instrument.clone()],
        quotes: vec![],
        orders: vec![],
        required_capabilities: vec![],
    };
    let latency = StaticLatencyModel::new(
        DurationNanos::new(0),
        DurationNanos::new(request.insert_latency_ns),
        DurationNanos::new(0),
        DurationNanos::new(request.cancel_latency_ns),
    );
    let mut engine = create_engine_with_depth(
        &base,
        currency,
        true,
        BookType::L2_MBP,
        Some(LatencyModelHandle::new(latency)),
    )?;
    let state = Rc::new(RefCell::new(DepthState::default()));
    engine
        .0
        .add_strategy(DepthStrategy::new(request, state.clone())?)?;
    let instrument = InstrumentId::from(format!("{}.SIM", request.instrument.symbol));
    let precision = request.instrument.price_precision;
    let mut data = Vec::new();
    let mut bids = BTreeMap::new();
    let mut asks = BTreeMap::new();
    for e in &request.events {
        if e.kind.as_str() == "trade" {
            data.push(Data::Trade(TradeTick::new_checked(
                instrument,
                Price::from_decimal_dp(decimal(e.trade_price.as_deref().unwrap())?, precision)?,
                Quantity::from_decimal_dp(decimal(e.trade_quantity.as_deref().unwrap())?, 0)?,
                if e.aggressor.as_deref() == Some("buy") {
                    AggressorSide::Buy
                } else {
                    AggressorSide::Sell
                },
                TradeId::from(e.trade_id.as_deref().unwrap()),
                e.ts_ns.into(),
                e.available_ns.into(),
            )?));
            continue;
        }
        let mut deltas = Vec::new();
        if e.kind.as_str() == "snapshot" {
            bids.clear();
            asks.clear();
            deltas.push(OrderBookDelta::clear(
                instrument,
                e.sequence,
                e.ts_ns.into(),
                e.available_ns.into(),
            ));
        }
        for (levels, book, side) in [
            (&e.bids, &mut bids, OrderSide::Buy),
            (&e.asks, &mut asks, OrderSide::Sell),
        ] {
            for l in levels {
                let p = decimal(&l.price)?;
                let q = decimal(&l.quantity)?;
                let action = if q.is_zero() {
                    BookAction::Delete
                } else if book.contains_key(&p) {
                    BookAction::Update
                } else {
                    BookAction::Add
                };
                if q.is_zero() {
                    book.remove(&p);
                } else {
                    book.insert(p, q);
                }
                deltas.push(OrderBookDelta::new(
                    instrument,
                    action,
                    BookOrder::new(
                        side,
                        Price::from_decimal_dp(p, precision)?,
                        Quantity::from_decimal_dp(q, 0)?,
                        0,
                    ),
                    0,
                    e.sequence,
                    e.ts_ns.into(),
                    e.available_ns.into(),
                ));
            }
        }
        if let Some(last) = deltas.last_mut() {
            last.flags |= RecordFlag::F_LAST as u8;
        }
        if !deltas.is_empty() {
            data.push(Data::BookDeltas(
                OrderBookDeltas::new(instrument, deltas).into(),
            ));
        }
    }
    engine.0.add_data(data, None, true, true)?;
    engine
        .0
        .run(None, Some(request.end_ns.into()), None, false)?;
    let mark = (*bids.last_key_value().unwrap().0 + *asks.first_key_value().unwrap().0)
        / rust_decimal::Decimal::from(2);
    let marks = BTreeMap::from([(request.instrument.symbol.as_str(), mark)]);
    ensure!(
        state.borrow().decisions.len() == request.commands.len(),
        "not all declared decision events were processed"
    );
    let mut account = snapshot(&engine, &state.borrow().intents, &marks, currency)?;
    account.schema_version = "engine_depth_account.v1".into();
    account.capabilities = DEPTH_CAPABILITIES.iter().map(|s| (*s).into()).collect();
    let mut receipts = Vec::new();
    {
        use nautilus_model::{events::OrderEventAny, identifiers::ClientOrderId, orders::Order};
        let cache = engine.0.kernel().cache.borrow();
        for intent in &state.borrow().intents {
            if let Some(order) = cache.order(&ClientOrderId::from(intent.id.as_str())) {
                for event in order.events() {
                    macro_rules! receipt {
                        ($e:expr,$kind:expr,$trade:expr,$fill:expr) => {
                            receipts.push(DepthReceipt {
                                order_id: intent.id.clone(),
                                kind: $kind.into(),
                                ts_ns: $e.ts_event.as_u64(),
                                received_ns: $e.ts_init.as_u64(),
                                trade_id: $trade,
                                fill: $fill,
                            })
                        };
                    }
                    match event {
                        OrderEventAny::Filled(e) => receipt!(
                            e,
                            "filled",
                            Some(e.trade_id.to_string()),
                            Some(crate::contract::Fill {
                                order_id: intent.id.clone(),
                                symbol: intent.symbol.clone(),
                                side: if e.order_side == OrderSide::Buy {
                                    crate::contract::Side::Buy
                                } else {
                                    crate::contract::Side::Sell
                                },
                                ts_ns: e.ts_event.as_u64(),
                                quantity: e.last_qty.as_decimal().normalize().to_string(),
                                price: e.last_px.as_decimal().normalize().to_string(),
                                commission: e.commission.map_or_else(
                                    || "0".into(),
                                    |m| m.as_decimal().normalize().to_string()
                                )
                            })
                        ),
                        OrderEventAny::Accepted(e) => receipt!(e, "accepted", None, None),
                        OrderEventAny::Canceled(e) => receipt!(e, "canceled", None, None),
                        OrderEventAny::CancelRejected(e) => {
                            receipt!(e, "cancel_rejected", None, None)
                        }
                        OrderEventAny::Rejected(e) => receipt!(e, "rejected", None, None),
                        OrderEventAny::Denied(e) => receipt!(e, "denied", None, None),
                        _ => {}
                    }
                }
            }
        }
    }
    receipts.sort_by_key(|r| (r.received_ns, r.ts_ns));
    Ok(DepthResult {
        schema_version: "engine_depth_result.v1".into(),
        request_sha256: crate::depth_contract::request_digest(request)?,
        capabilities: account.capabilities.clone(),
        decisions: state.borrow().decisions.clone(),
        receipts,
        fill_order: state.borrow().fill_order.clone(),
        valuation_ns: request
            .events
            .iter()
            .rev()
            .find(|e| e.kind.as_str() != "trade")
            .unwrap()
            .available_ns,
        observation_ns: request.end_ns,
        account,
    })
}
