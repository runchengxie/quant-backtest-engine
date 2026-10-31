//! Translates precomputed intents; contains no portfolio selection or matching logic.
use crate::contract::{Request, Side, decimal};
use anyhow::Result;
use nautilus_common::actor::DataActor;
use nautilus_model::{
    data::QuoteTick,
    enums::OrderSide,
    identifiers::{ClientOrderId, InstrumentId},
    types::Quantity,
};
use nautilus_trading::{
    nautilus_strategy,
    strategy::{Strategy, StrategyConfig, StrategyCore},
};

#[derive(Debug)]
pub(crate) struct IntentStrategy {
    core: StrategyCore,
    instruments: Vec<InstrumentId>,
    pending: Vec<Pending>,
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
            self.submit_order(order, None, None, None)?;
        }
        Ok(())
    }
}
