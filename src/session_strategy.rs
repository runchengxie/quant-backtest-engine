//! Rule admission state derives eligibility from upstream fills, never cash accounting.
use crate::{
    contract::{Side, decimal},
    session_contract::{SessionQuote, SessionRequest},
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
use std::{cell::RefCell, collections::BTreeMap, rc::Rc};

#[derive(Debug, Default)]
pub(crate) struct SessionState {
    pub current: usize,
    pub sellable: BTreeMap<InstrumentId, Decimal>,
    pub reservations: BTreeMap<ClientOrderId, (InstrumentId, Decimal)>,
}
impl SessionState {
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
    session: usize,
    id: ClientOrderId,
    instrument: InstrumentId,
    information_ts_ns: u64,
    side: OrderSide,
    quantity: Quantity,
}
#[derive(Debug)]
pub(crate) struct SessionStrategy {
    core: StrategyCore,
    pending: Vec<Pending>,
    instruments: Vec<InstrumentId>,
    rules: BTreeMap<(InstrumentId, u64), SessionQuote>,
    lots: BTreeMap<InstrumentId, u32>,
    state: Rc<RefCell<SessionState>>,
    currency: Currency,
    fee: Decimal,
    enforce_t1: bool,
}
impl SessionStrategy {
    pub fn new(
        request: &SessionRequest,
        state: Rc<RefCell<SessionState>>,
        currency: Currency,
    ) -> Result<Self> {
        let mut pending = Vec::new();
        let mut rules = BTreeMap::new();
        for (session, s) in request.sessions.iter().enumerate() {
            for q in &s.quotes {
                rules.insert(
                    (InstrumentId::from(format!("{}.SIM", q.symbol)), q.ts_ns),
                    q.clone(),
                );
            }
            for o in &s.orders {
                pending.push(Pending {
                    session,
                    id: ClientOrderId::from(o.id.as_str()),
                    instrument: InstrumentId::from(format!("{}.SIM", o.symbol)),
                    information_ts_ns: o.information_ts_ns,
                    side: if o.side == Side::Buy {
                        OrderSide::Buy
                    } else {
                        OrderSide::Sell
                    },
                    quantity: Quantity::from_decimal_dp(decimal(&o.quantity)?, 0)?,
                });
            }
        }
        let lots = request
            .instruments
            .iter()
            .map(|i| (InstrumentId::from(format!("{}.SIM", i.symbol)), i.buy_lot))
            .collect::<BTreeMap<_, _>>();
        Ok(Self {
            core: StrategyCore::new(StrategyConfig::default()),
            pending,
            instruments: lots.keys().copied().collect(),
            rules,
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
        let rule = self
            .rules
            .get(&(quote.instrument_id, quote.ts_event.as_u64()))
            .context("session rule missing")?
            .clone();
        let instrument = self
            .cache()
            .instrument(&quote.instrument_id)
            .context("instrument missing")?;
        let mut cash = self
            .cache()
            .account_for_venue(&quote.instrument_id.venue)
            .context("account missing")?
            .balance_free(Some(self.currency))
            .context("cash balance missing")?
            .as_decimal();
        let mut index = 0;
        while index < self.pending.len() {
            let p = &self.pending[index];
            if p.session != self.state.borrow().current
                || p.instrument != quote.instrument_id
                || p.information_ts_ns >= quote.ts_event.as_u64()
            {
                index += 1;
                continue;
            }
            let p = self.pending.remove(index);
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
        Ok(())
    }
}
