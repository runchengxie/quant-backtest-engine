//! Direct upstream integration. All fills and cash balances originate in Nautilus.
use crate::{
    BacktestResult, Request,
    contract::{CAPABILITIES, Fill, OrderResult, Position, decimal},
    strategy::IntentStrategy,
};
use anyhow::{Context, Result, ensure};
use nautilus_backtest::{
    config::{BacktestEngineConfig, SimulatedVenueConfig},
    engine::BacktestEngine,
};
use nautilus_execution::models::fee::{FeeModelAny, MakerTakerFeeModel};
use nautilus_model::{
    accounts::Account,
    data::{Data, QuoteTick},
    enums::{AccountType, BookType, OmsType, PositionSide},
    events::OrderEventAny,
    identifiers::{ClientOrderId, InstrumentId, Symbol, Venue},
    instruments::{Equity, InstrumentAny},
    orders::Order,
    types::{Currency, Money, Price, Quantity},
};
use rust_decimal::Decimal;
use std::collections::BTreeMap;

pub(crate) struct Engine(pub(crate) BacktestEngine);
impl Drop for Engine {
    fn drop(&mut self) {
        self.0.dispose();
    }
}
fn text(d: Decimal) -> String {
    d.normalize().to_string()
}

pub(crate) fn create_engine(
    request: &Request,
    currency: Currency,
    liquidity: bool,
) -> Result<Engine> {
    let config = BacktestEngineConfig {
        bypass_logging: true,
        logging: nautilus_common::logging::logger::LoggerConfig {
            bypass_logging: true,
            ..Default::default()
        },
        run_analysis: false,
        ..Default::default()
    };
    let mut engine = Engine(BacktestEngine::new(config)?);
    let venue = Venue::from("SIM");
    let fee = decimal(&request.fee_bps)? / Decimal::from(10000);
    engine.0.add_venue(
        SimulatedVenueConfig::builder()
            .venue(venue)
            .oms_type(OmsType::Netting)
            .account_type(AccountType::Cash)
            .base_currency(currency)
            .book_type(BookType::L1_MBP)
            .liquidity_consumption(liquidity)
            .starting_balances(vec![Money::from_decimal(
                decimal(&request.initial_cash)?,
                currency,
            )?])
            .fee_model(FeeModelAny::MakerTaker(MakerTakerFeeModel::new(fee, fee)).into())
            .build()?,
    )?;
    for i in &request.instruments {
        let instrument = Equity::builder()
            .instrument_id(InstrumentId::from(format!("{}.SIM", i.symbol)))
            .raw_symbol(Symbol::from(i.symbol.as_str()))
            .currency(currency)
            .price_precision(i.price_precision)
            .price_increment(Price::from_decimal_dp(
                Decimal::new(1, i.price_precision.into()),
                i.price_precision,
            )?)
            .lot_size(Quantity::from(1))
            .ts_event(0.into())
            .ts_init(0.into())
            .build()?;
        engine
            .0
            .add_instrument(&InstrumentAny::Equity(instrument))?;
    }
    Ok(engine)
}

pub(crate) fn execute(request: &Request) -> Result<BacktestResult> {
    let mut engine = create_engine(request, Currency::USD(), false)?;
    let precisions: BTreeMap<_, _> = request
        .instruments
        .iter()
        .map(|i| (i.symbol.as_str(), i.price_precision))
        .collect();
    engine.0.add_strategy(IntentStrategy::new(request)?)?;
    let mut data = Vec::with_capacity(request.quotes.len());
    let mut marks = BTreeMap::new();
    for q in &request.quotes {
        let precision = precisions[q.symbol.as_str()];
        let bid = decimal(&q.bid)?;
        let ask = decimal(&q.ask)?;
        marks.insert(q.symbol.as_str(), (bid + ask) / Decimal::from(2));
        data.push(Data::Quote(QuoteTick::new(
            InstrumentId::from(format!("{}.SIM", q.symbol)),
            Price::from_decimal_dp(bid, precision)?,
            Price::from_decimal_dp(ask, precision)?,
            Quantity::from(1_000_000),
            Quantity::from(1_000_000),
            q.ts_ns.into(),
            q.ts_ns.into(),
        )));
    }
    engine.0.add_data(data, None, true, true)?;
    engine.0.run(None, None, None, false)?;
    snapshot(&engine, &request.orders, &marks, Currency::USD())
}

pub(crate) fn snapshot(
    engine: &Engine,
    intents: &[crate::contract::OrderIntent],
    marks: &BTreeMap<&str, Decimal>,
    currency: Currency,
) -> Result<BacktestResult> {
    let cache = engine.0.kernel().cache.borrow();
    let venue = Venue::from("SIM");
    let account = cache
        .account_for_venue(&venue)
        .context("upstream account missing")?;
    let cash = account
        .balance_total(Some(currency))
        .context("upstream account-currency balance missing")?
        .as_decimal();
    let mut orders = Vec::new();
    let mut fills = Vec::new();
    let mut commission = Decimal::ZERO;
    for intent in intents {
        let Some(order) = cache.order(&ClientOrderId::from(intent.id.as_str())) else {
            orders.push(OrderResult {
                id: intent.id.clone(),
                symbol: intent.symbol.clone(),
                status: "NOT_SUBMITTED".into(),
                filled_quantity: "0".into(),
            });
            continue;
        };
        orders.push(OrderResult {
            id: intent.id.clone(),
            symbol: intent.symbol.clone(),
            status: order.status().to_string(),
            filled_quantity: text(order.filled_qty().as_decimal()),
        });
        for event in order.events() {
            if let OrderEventAny::Filled(f) = event {
                let cost = f.commission.map_or(Decimal::ZERO, |m| m.as_decimal());
                commission += cost;
                fills.push(Fill {
                    order_id: intent.id.clone(),
                    symbol: intent.symbol.clone(),
                    side: intent.side,
                    ts_ns: f.ts_event.as_u64(),
                    quantity: text(f.last_qty.as_decimal()),
                    price: text(f.last_px.as_decimal()),
                    commission: text(cost),
                });
            }
        }
    }
    fills.sort_by(|a, b| (a.ts_ns, &a.order_id).cmp(&(b.ts_ns, &b.order_id)));
    let mut positions = Vec::new();
    let mut positions_value = Decimal::ZERO;
    for p in cache.positions_open(None, None, None, None, None) {
        ensure!(
            p.side == PositionSide::Long,
            "unexpected short position from cash-only engine"
        );
        let symbol = p.instrument_id.symbol.to_string();
        let mark = *marks
            .get(symbol.as_str())
            .context("position mark missing")?;
        let quantity = p.quantity.as_decimal();
        let value = quantity * mark;
        positions_value += value;
        positions.push(Position {
            symbol,
            quantity: text(quantity),
            mark_price: text(mark),
            market_value: text(value),
        });
    }
    positions.sort_by(|a, b| a.symbol.cmp(&b.symbol));
    Ok(BacktestResult {
        schema_version: "engine_result.v1".into(),
        backend: "nautilus".into(),
        backend_version: "0.66.0".into(),
        capabilities: CAPABILITIES.iter().map(|s| (*s).into()).collect(),
        currency: currency.to_string(),
        cash: text(cash),
        positions_value: text(positions_value),
        equity: text(cash + positions_value),
        commission: text(commission),
        orders,
        fills,
        positions,
    })
}
