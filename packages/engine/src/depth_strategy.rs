//! Account-feedback decisions read the authoritative upstream cache at each eligible event.
use crate::{
    contract::{OrderIntent, Side, decimal},
    depth_contract::{DepthCommand, DepthDecision, DepthRequest},
};
use anyhow::{Context, Result};
use nautilus_common::{
    actor::DataActor,
    timer::{TimeEvent, TimeEventCallback},
};
use nautilus_model::{
    accounts::Account,
    data::{OrderBookDeltas, TradeTick},
    enums::{BookType, OrderSide},
    events::OrderFilled,
    fees::calculate_maker_taker_commission,
    identifiers::{ClientOrderId, InstrumentId},
    instruments::Instrument,
    orders::Order,
    types::{Currency, Price, Quantity},
};
use nautilus_trading::{
    nautilus_strategy,
    strategy::{Strategy, StrategyConfig, StrategyCore},
};
use rust_decimal::Decimal;
use std::{
    cell::RefCell,
    collections::{BTreeMap, BTreeSet, VecDeque},
    rc::Rc,
};
#[derive(Debug, Default)]
pub(crate) struct DepthState {
    pub intents: Vec<OrderIntent>,
    pub decisions: Vec<DepthDecision>,
    pub fill_order: Vec<String>,
}
#[derive(Debug)]
pub(crate) struct DepthStrategy {
    core: StrategyCore,
    instrument: InstrumentId,
    currency: Currency,
    precision: u8,
    fee: Decimal,
    arrival_alerts: Vec<u64>,
    commands: BTreeMap<u64, DepthCommand>,
    event_sequences: BTreeMap<u64, VecDeque<u64>>,
    state: Rc<RefCell<DepthState>>,
}
impl DepthStrategy {
    pub(crate) fn new(request: &DepthRequest, state: Rc<RefCell<DepthState>>) -> Result<Self> {
        let mut event_sequences: BTreeMap<u64, VecDeque<u64>> = BTreeMap::new();
        for e in &request.events {
            event_sequences
                .entry(e.available_ns)
                .or_default()
                .push_back(e.sequence);
        }
        let event_times = request
            .events
            .iter()
            .map(|event| (event.sequence, event.available_ns))
            .collect::<BTreeMap<_, _>>();
        Ok(Self {
            core: StrategyCore::new(StrategyConfig::default()),
            instrument: InstrumentId::from(format!("{}.SIM", request.instrument.symbol)),
            currency: if request.currency == "CNY" {
                Currency::CNY()
            } else {
                Currency::USD()
            },
            precision: request.instrument.price_precision,
            fee: decimal(&request.fee_bps)? / Decimal::from(10000),
            arrival_alerts: request
                .commands
                .iter()
                .filter_map(|command| {
                    let delay = if command.action.as_str() == "cancel" {
                        request.cancel_latency_ns
                    } else {
                        request.insert_latency_ns
                    };
                    if delay == 0 {
                        None
                    } else {
                        Some(event_times[&command.event_sequence] + delay)
                    }
                })
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect(),
            commands: request
                .commands
                .iter()
                .cloned()
                .map(|c| (c.event_sequence, c))
                .collect(),
            event_sequences,
            state,
        })
    }
    fn process(&mut self, ts: u64) -> Result<()> {
        let Some(seqs) = self.event_sequences.get_mut(&ts) else {
            return Ok(());
        };
        let Some(seq) = seqs.pop_front() else {
            return Ok(());
        };
        let Some(c) = self.commands.remove(&seq) else {
            return Ok(());
        };
        let (held, free, admissible, total, locked, working_ids, sell_working) = {
            let cache = self.cache();
            let held = cache
                .positions_open(None, Some(&self.instrument), None, None, None)
                .iter()
                .map(|p| p.quantity.as_decimal())
                .sum::<Decimal>();
            let account = cache
                .account_for_venue(&self.instrument.venue)
                .context("account missing")?;
            let free = account
                .balance_free(Some(self.currency))
                .context("free balance missing")?
                .as_decimal();
            let total = account
                .balance_total(Some(self.currency))
                .context("total balance missing")?
                .as_decimal();
            let locked = account
                .balance_locked(Some(self.currency))
                .context("locked balance missing")?
                .as_decimal();
            let mut orders = cache.orders_open(None, Some(&self.instrument), None, None, None);
            orders.extend(cache.orders_inflight(None, Some(&self.instrument), None, None, None));
            let mut seen = BTreeSet::new();
            orders.retain(|order| seen.insert(order.client_order_id()));
            let mut working_ids = orders
                .iter()
                .filter(|o| !o.is_closed())
                .map(|o| o.client_order_id().to_string())
                .collect::<Vec<_>>();
            working_ids.sort();
            let sell_working = orders
                .iter()
                .filter(|o| !o.is_closed() && o.order_side() == OrderSide::Sell)
                .map(|o| o.leaves_qty().as_decimal())
                .sum::<Decimal>();
            let instrument = cache
                .instrument(&self.instrument)
                .context("instrument missing")?;
            let mut reserved_buys = Decimal::ZERO;
            for order in orders
                .iter()
                .filter(|o| !o.is_closed() && o.order_side() == OrderSide::Buy)
            {
                let quantity = order.leaves_qty();
                let price = order.price().context("working limit price missing")?;
                reserved_buys += instrument
                    .try_calculate_notional_value(quantity, price, Some(false))?
                    .as_decimal()
                    + calculate_maker_taker_commission(
                        &instrument,
                        quantity,
                        price,
                        self.fee,
                        Some(false),
                    )?
                    .as_decimal();
            }
            let admissible = free.min((total - reserved_buys).max(Decimal::ZERO));
            (
                held,
                free,
                admissible,
                total,
                locked,
                working_ids,
                sell_working,
            )
        };
        let mut d = DepthDecision {
            id: c.id.clone(),
            ts_ns: ts,
            action: c.action.as_str().into(),
            held_quantity: held.normalize().to_string(),
            free_cash: free.normalize().to_string(),
            admissible_cash: admissible.normalize().to_string(),
            total_cash: total.normalize().to_string(),
            locked_cash: locked.normalize().to_string(),
            observed_fill_count: self.state.borrow().fill_order.len() as u64,
            working_order_ids: working_ids.clone(),
            submitted_quantity: "0".into(),
            outcome: String::new(),
        };
        if c.action.as_str() == "cancel" {
            let id = ClientOrderId::from(c.cancel_id.as_deref().unwrap());
            let active = self.cache().order(&id).is_some_and(|o| !o.is_closed());
            if active {
                self.cancel_order(id, None, None)?;
                d.outcome = "cancel_requested".into();
            } else {
                d.outcome = "not_working".into();
            }
        } else {
            let requested = decimal(&c.quantity)?;
            let signed = match c.action.as_str() {
                "buy" => requested,
                "sell" => -requested,
                _ => requested - held,
            };
            if c.action.as_str() == "target" && !working_ids.is_empty() {
                d.outcome = "waiting_for_working_order".into();
            } else if signed == Decimal::ZERO {
                d.outcome = "target_already_held".into();
            } else {
                let side = if signed > Decimal::ZERO {
                    OrderSide::Buy
                } else {
                    OrderSide::Sell
                };
                let qty = signed.abs();
                let price = decimal(&c.limit_price)?;
                let order = self.order().limit(
                    self.instrument,
                    side,
                    Quantity::from_decimal_dp(qty, 0)?,
                    Price::from_decimal_dp(price, self.precision)?,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    Some(ClientOrderId::from(c.id.as_str())),
                );
                self.state.borrow_mut().intents.push(OrderIntent {
                    id: c.id.clone(),
                    symbol: self.instrument.symbol.to_string(),
                    information_ts_ns: c.information_ts_ns,
                    side: if side == OrderSide::Buy {
                        Side::Buy
                    } else {
                        Side::Sell
                    },
                    quantity: qty.normalize().to_string(),
                });
                let instrument = self
                    .cache()
                    .instrument(&self.instrument)
                    .context("instrument missing")?;
                let required = instrument
                    .try_calculate_notional_value(
                        Quantity::from_decimal_dp(qty, 0)?,
                        Price::from_decimal_dp(price, self.precision)?,
                        Some(false),
                    )?
                    .as_decimal()
                    + calculate_maker_taker_commission(
                        &instrument,
                        Quantity::from_decimal_dp(qty, 0)?,
                        Price::from_decimal_dp(price, self.precision)?,
                        self.fee,
                        Some(false),
                    )?
                    .as_decimal();
                if side == OrderSide::Buy && required > admissible {
                    self.deny_order(&order, "INSUFFICIENT_CASH_INCLUDING_FEES".into());
                    d.outcome = "denied_cash".into();
                } else if side == OrderSide::Sell && qty > held - sell_working {
                    self.deny_order(&order, "INSUFFICIENT_AVAILABLE_SHARES".into());
                    d.outcome = "denied_shares".into();
                } else {
                    self.submit_order(order, None, None, None)?;
                    d.submitted_quantity = qty.normalize().to_string();
                    d.outcome = "submitted".into();
                }
            }
        }
        self.state.borrow_mut().decisions.push(d);
        Ok(())
    }
}
nautilus_strategy!(DepthStrategy, {
    fn on_order_filled(&mut self, event: &OrderFilled) {
        self.state
            .borrow_mut()
            .fill_order
            .push(event.trade_id.to_string());
    }
});
impl DataActor for DepthStrategy {
    fn on_start(&mut self) -> Result<()> {
        for arrival in &self.arrival_alerts {
            self.clock().set_time_alert_ns(
                &format!("DEPTH-ARRIVAL-{arrival}"),
                (*arrival).into(),
                Some(TimeEventCallback::from(|_: TimeEvent| {})),
                Some(false),
            )?;
        }
        self.subscribe_book_deltas(self.instrument, BookType::L2_MBP, None, None, false, None);
        self.subscribe_trades(self.instrument, None, None);
        Ok(())
    }
    fn on_book_deltas(&mut self, e: &OrderBookDeltas) -> Result<()> {
        self.process(e.ts_init.as_u64())
    }
    fn on_trade(&mut self, e: &TradeTick) -> Result<()> {
        self.process(e.ts_init.as_u64())
    }
}
