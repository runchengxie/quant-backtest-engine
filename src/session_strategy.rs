//! Rule admission state derives eligibility from upstream fills, never cash accounting.
use crate::{
    contract::{Side, decimal},
    session_contract::{MarketSession, SessionConfig, SessionQuote},
};
use anyhow::{Context, Result};
use nautilus_common::actor::DataActor;
use nautilus_model::{
    accounts::Account,
    data::QuoteTick,
    enums::{OrderSide, TimeInForce},
    events::{OrderCanceled, OrderDenied, OrderExpired, OrderFilled, OrderRejected},
    fees::calculate_maker_taker_commission,
    identifiers::{ClientOrderId, InstrumentId},
    instruments::Instrument,
    types::{Currency, Quantity},
};
use nautilus_trading::{
    nautilus_strategy,
    strategy::{Strategy, StrategyConfig, StrategyCore},
};
use rust_decimal::Decimal;
use std::{cell::RefCell, collections::BTreeMap, rc::Rc, time::Instant};

#[derive(Debug, Default)]
pub(crate) struct SessionState {
    pending: BTreeMap<InstrumentId, Vec<Pending>>,
    rules: BTreeMap<(InstrumentId, u64), SessionQuote>,
    pub profile: bool,
    pub quote_callbacks: u64,
    pub pending_checks: u64,
    pub cache_reads: u64,
    pub rule_seconds: f64,
    pub cache_seconds: f64,
    pub instrument_seconds: f64,
    pub pending_seconds: f64,
    pub sellable: BTreeMap<InstrumentId, Decimal>,
    pub reservations: BTreeMap<ClientOrderId, (InstrumentId, Decimal)>,
}
impl SessionState {
    pub(crate) fn load(&mut self, session: &MarketSession) -> Result<()> {
        let mut pending: BTreeMap<_, Vec<_>> = BTreeMap::new();
        let mut rules = BTreeMap::new();
        for q in &session.quotes {
            rules.insert(
                (InstrumentId::from(format!("{}.SIM", q.symbol)), q.ts_ns),
                q.clone(),
            );
        }
        for o in &session.orders {
            let instrument = InstrumentId::from(format!("{}.SIM", o.symbol));
            pending.entry(instrument).or_default().push(Pending {
                id: ClientOrderId::from(o.id.as_str()),
                instrument,
                information_ts_ns: o.information_ts_ns,
                side: if o.side == Side::Buy {
                    OrderSide::Buy
                } else {
                    OrderSide::Sell
                },
                quantity: Quantity::from_decimal_dp(decimal(&o.quantity)?, 0)?,
            });
        }
        self.pending = pending;
        self.rules = rules;
        Ok(())
    }
    pub(crate) fn clear_input(&mut self) {
        self.pending.clear();
        self.rules.clear();
    }

    fn release(&mut self, id: ClientOrderId) {
        if let Some((instrument, remaining)) = self.reservations.remove(&id) {
            *self.sellable.entry(instrument).or_default() += remaining;
        }
    }
    fn filled(&mut self, event: &OrderFilled, enforce_t1: bool) {
        if event.order_side == OrderSide::Buy && !enforce_t1 {
            *self.sellable.entry(event.instrument_id).or_default() += event.last_qty.as_decimal();
        }
        if let Some((_, remaining)) = self.reservations.get_mut(&event.client_order_id) {
            *remaining -= event.last_qty.as_decimal();
        }
    }
}
#[derive(Debug)]
struct Pending {
    id: ClientOrderId,
    instrument: InstrumentId,
    information_ts_ns: u64,
    side: OrderSide,
    quantity: Quantity,
}
#[derive(Debug)]
pub(crate) struct SessionStrategy {
    core: StrategyCore,
    instruments: Vec<InstrumentId>,
    lots: BTreeMap<InstrumentId, u32>,
    state: Rc<RefCell<SessionState>>,
    currency: Currency,
    fee: Decimal,
    enforce_t1: bool,
}
impl SessionStrategy {
    pub fn new(
        request: &SessionConfig,
        state: Rc<RefCell<SessionState>>,
        currency: Currency,
    ) -> Result<Self> {
        let lots = request
            .instruments
            .iter()
            .map(|i| (InstrumentId::from(format!("{}.SIM", i.symbol)), i.buy_lot))
            .collect::<BTreeMap<_, _>>();
        Ok(Self {
            core: StrategyCore::new(StrategyConfig::default()),
            instruments: lots.keys().copied().collect(),
            lots,
            state,
            currency,
            fee: decimal(&request.fee_bps)? / Decimal::from(10000),
            enforce_t1: request.enforce_t1,
        })
    }
}
nautilus_strategy!(SessionStrategy, {
    fn on_order_filled(&mut self, event: &OrderFilled) {
        self.state.borrow_mut().filled(event, self.enforce_t1);
    }
    fn on_order_canceled(&mut self, event: &OrderCanceled) {
        self.state.borrow_mut().release(event.client_order_id);
    }
    fn on_order_denied(&mut self, event: OrderDenied) {
        self.state.borrow_mut().release(event.client_order_id);
    }
    fn on_order_rejected(&mut self, event: OrderRejected) {
        self.state.borrow_mut().release(event.client_order_id);
    }
    fn on_order_expired(&mut self, event: OrderExpired) {
        self.state.borrow_mut().release(event.client_order_id);
    }
});
impl DataActor for SessionStrategy {
    fn on_start(&mut self) -> Result<()> {
        for instrument in self.instruments.clone() {
            self.subscribe_quotes(instrument, None, None);
        }
        Ok(())
    }
    fn on_stop(&mut self) -> Result<()> {
        for instrument in self.instruments.clone() {
            self.unsubscribe_quotes(instrument, None, None);
        }
        Ok(())
    }
    fn on_quote(&mut self, quote: &QuoteTick) -> Result<()> {
        let profile = self.state.borrow().profile;
        let started = profile.then(Instant::now);
        let key = quote.instrument_id;
        let mut checks = 0;
        let eligible = self
            .state
            .borrow()
            .pending
            .get(&key)
            .is_some_and(|pending| {
                pending.iter().any(|p| {
                    checks += u64::from(profile);
                    p.information_ts_ns < quote.ts_event.as_u64()
                })
            });
        if let Some(started) = started {
            let mut state = self.state.borrow_mut();
            state.quote_callbacks += 1;
            state.pending_checks += checks;
            state.pending_seconds += started.elapsed().as_secs_f64();
        }
        // Account snapshots contain growing event history. Only request one when
        // this quote can consume an intent; upstream still replays every quote.
        if !eligible {
            return Ok(());
        }
        let started = profile.then(Instant::now);
        let rule = self
            .state
            .borrow()
            .rules
            .get(&(quote.instrument_id, quote.ts_event.as_u64()))
            .context("session rule missing")?
            .clone();
        if let Some(started) = started {
            let mut state = self.state.borrow_mut();
            state.cache_reads += 1;
            state.rule_seconds += started.elapsed().as_secs_f64();
        }
        let started = profile.then(Instant::now);
        let instrument = self
            .cache()
            .instrument(&quote.instrument_id)
            .context("instrument missing")?;
        if let Some(started) = started {
            self.state.borrow_mut().instrument_seconds += started.elapsed().as_secs_f64();
        }
        let started = profile.then(Instant::now);
        let mut cash = self
            .cache()
            .account_for_venue(&quote.instrument_id.venue)
            .context("account missing")?
            .balance_free(Some(self.currency))
            .context("cash balance missing")?
            .as_decimal();
        if let Some(started) = started {
            self.state.borrow_mut().cache_seconds += started.elapsed().as_secs_f64();
        }
        let started = profile.then(Instant::now);
        let mut checks = 0;
        // A quote consumes only its session/instrument bucket. Iterate in
        // request order, retaining later-information intents in that same order;
        // sorting by information time would change cash/liquidity priority.
        let pending = self
            .state
            .borrow_mut()
            .pending
            .remove(&key)
            .expect("eligible pending bucket");
        let mut deferred = Vec::new();
        for p in pending {
            checks += u64::from(profile);
            if p.information_ts_ns >= quote.ts_event.as_u64() {
                deferred.push(p);
                continue;
            }
            let order = self.order().market(
                p.instrument,
                p.side,
                p.quantity,
                Some(TimeInForce::Ioc),
                None,
                None,
                None,
                None,
                None,
                Some(p.id),
            );
            let blocked = !rule.tradable
                || (p.side == OrderSide::Buy && rule.limit_up)
                || (p.side == OrderSide::Sell && rule.limit_down);
            if blocked {
                self.deny_order(&order, "QUOTE_TRADE_PERMISSION".into());
                continue;
            }
            if p.side == OrderSide::Buy {
                if p.quantity.as_decimal() % Decimal::from(self.lots[&p.instrument])
                    != Decimal::ZERO
                {
                    self.deny_order(&order, "BUY_LOT".into());
                    continue;
                }
                let notional = instrument
                    .try_calculate_notional_value(p.quantity, quote.ask_price, Some(false))?
                    .as_decimal();
                let fee = calculate_maker_taker_commission(
                    &instrument,
                    p.quantity,
                    quote.ask_price,
                    self.fee,
                    Some(false),
                )?
                .as_decimal();
                if notional + fee > cash {
                    self.deny_order(&order, "INSUFFICIENT_CASH_INCLUDING_FEES".into());
                    continue;
                }
                cash -= notional + fee;
            } else {
                let available = self
                    .state
                    .borrow()
                    .sellable
                    .get(&p.instrument)
                    .copied()
                    .unwrap_or_default();
                if p.quantity.as_decimal() > available {
                    self.deny_order(&order, "SELLABLE_QUANTITY".into());
                    continue;
                }
                let mut state = self.state.borrow_mut();
                *state.sellable.entry(p.instrument).or_default() -= p.quantity.as_decimal();
                state
                    .reservations
                    .insert(p.id, (p.instrument, p.quantity.as_decimal()));
            }
            self.submit_order(order, None, None, None)?;
        }
        if !deferred.is_empty() {
            self.state.borrow_mut().pending.insert(key, deferred);
        }
        if let Some(started) = started {
            let mut state = self.state.borrow_mut();
            state.pending_checks += checks;
            state.pending_seconds += started.elapsed().as_secs_f64();
        }
        Ok(())
    }
}
