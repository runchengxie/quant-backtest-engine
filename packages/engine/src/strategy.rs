//! Translates precomputed intents; contains no portfolio selection or matching logic.
use crate::contract::{Request, Side, decimal};
use anyhow::{Context, Result};
use nautilus_common::actor::DataActor;
use nautilus_model::{
    accounts::Account,
    data::QuoteTick,
    enums::OrderSide,
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

#[derive(Debug)]
pub(crate) struct IntentStrategy {
    core: StrategyCore,
    instruments: Vec<InstrumentId>,
    pending: Vec<Pending>,
    fee_rate: Decimal,
}
#[derive(Debug)]
struct Pending {
    instrument: InstrumentId,
    id: ClientOrderId,
    information_ts_ns: u64,
    side: OrderSide,
    quantity: Quantity,
}
impl IntentStrategy {
    pub fn new(request: &Request) -> Result<Self> {
        let instruments = request
            .instruments
            .iter()
            .map(|i| InstrumentId::from(format!("{}.SIM", i.symbol)))
            .collect();
        let pending = request
            .orders
            .iter()
            .map(|o| {
                Ok(Pending {
                    instrument: InstrumentId::from(format!("{}.SIM", o.symbol)),
                    id: ClientOrderId::from(o.id.as_str()),
                    information_ts_ns: o.information_ts_ns,
                    side: if o.side == Side::Buy {
                        OrderSide::Buy
                    } else {
                        OrderSide::Sell
                    },
                    quantity: Quantity::from_decimal_dp(decimal(&o.quantity)?, 0)?,
                })
            })
            .collect::<Result<Vec<_>>>()?;
        Ok(Self {
            core: StrategyCore::new(StrategyConfig::default()),
            instruments,
            pending,
            fee_rate: decimal(&request.fee_bps)? / Decimal::from(10000),
        })
    }
}
nautilus_strategy!(IntentStrategy);
impl DataActor for IntentStrategy {
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
        // Reserve cash for buys queued in this callback. Sell proceeds become
        // available only after upstream processes the submitted orders.
        let account = self
            .cache()
            .account_for_venue(&quote.instrument_id.venue)
            .context("upstream account missing")?;
        let mut available = account
            .balance_free(Some(Currency::USD()))
            .context("upstream USD free balance missing")?
            .as_decimal();
        let instrument = self
            .cache()
            .instrument(&quote.instrument_id)
            .context("upstream instrument missing")?;
        let mut index = 0;
        while index < self.pending.len() {
            let p = &self.pending[index];
            if p.instrument != quote.instrument_id || p.information_ts_ns >= quote.ts_event.as_u64()
            {
                index += 1;
                continue;
            }
            let p = self.pending.remove(index);
            let order = self.order().market(
                p.instrument,
                p.side,
                p.quantity,
                None,
                None,
                None,
                None,
                None,
                None,
                Some(p.id),
            );
            if p.side == OrderSide::Buy {
                let notional = instrument
                    .try_calculate_notional_value(p.quantity, quote.ask_price, Some(false))?
                    .as_decimal();
                let fee = calculate_maker_taker_commission(
                    &instrument,
                    p.quantity,
                    quote.ask_price,
                    self.fee_rate,
                    Some(false),
                )?
                .as_decimal();
                let required = notional + fee;
                if required > available {
                    self.deny_order(&order, "INSUFFICIENT_CASH_INCLUDING_FEES".into());
                    continue;
                }
                available -= required;
            }
            self.submit_order(order, None, None, None)?;
        }
        Ok(())
    }
}
