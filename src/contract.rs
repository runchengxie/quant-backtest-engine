//! Versioned, framework-independent wire contract. Decimal values stay strings.
use anyhow::{Context, Result, ensure};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    str::FromStr,
};

pub const CAPABILITIES: &[&str] = &[
    "quote_market_orders",
    "multi_asset",
    "final_balances",
    "proportional_fees",
];
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub schema_version: String,
    pub initial_cash: String,
    pub fee_bps: String,
    pub instruments: Vec<Instrument>,
    pub quotes: Vec<Quote>,
    pub orders: Vec<OrderIntent>,
    pub required_capabilities: Vec<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Instrument {
    pub symbol: String,
    pub price_precision: u8,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Quote {
    pub symbol: String,
    pub ts_ns: u64,
    pub bid: String,
    pub ask: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct OrderIntent {
    pub id: String,
    pub symbol: String,
    pub information_ts_ns: u64,
    pub side: Side,
    pub quantity: String,
}
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Side {
    Buy,
    Sell,
}

pub(crate) fn decimal(value: &str) -> Result<Decimal> {
    ensure!(
        !value.is_empty()
            && value
                .bytes()
                .all(|b| b.is_ascii_digit() || b == b'.' || b == b'-'),
        "invalid decimal: {value}"
    );
    Decimal::from_str(value).with_context(|| format!("invalid decimal: {value}"))
}
fn amount(value: &str, precision: u32, max: i64, positive: bool) -> Result<Decimal> {
    let d = decimal(value)?;
    ensure!(
        d.scale() <= precision
            && d >= Decimal::ZERO
            && (!positive || d > Decimal::ZERO)
            && d <= Decimal::from(max),
        "decimal outside supported range or precision: {value}"
    );
    Ok(d)
}
fn identifier(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 40
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
}
fn timestamp(t: u64) -> Result<()> {
    ensure!(
        t > 0 && t <= 4_102_444_800_000_000_000,
        "timestamp must be UTC nanoseconds after epoch and no later than 2100-01-01"
    );
    Ok(())
}
impl Request {
    pub fn validate(&self) -> Result<()> {
        ensure!(
            self.schema_version == "engine_request.v1",
            "unsupported request schema"
        );
        amount(&self.initial_cash, 2, 1_000_000_000_000, true)?;
        amount(&self.fee_bps, 4, 10000, false)?;
        for c in &self.required_capabilities {
            ensure!(
                CAPABILITIES.contains(&c.as_str()),
                "unsupported capability: {c}"
            );
        }
        ensure!(
            !self.instruments.is_empty() && !self.quotes.is_empty(),
            "instruments and quotes must not be empty"
        );
        let mut instruments = BTreeMap::new();
        for i in &self.instruments {
            ensure!(
                identifier(&i.symbol) && i.price_precision <= 4,
                "invalid instrument or price precision"
            );
            ensure!(
                instruments
                    .insert(i.symbol.as_str(), i.price_precision)
                    .is_none(),
                "duplicate instrument"
            );
        }
        let mut last = BTreeMap::new();
        let mut global = 0;
        for q in &self.quotes {
            timestamp(q.ts_ns)?;
            let precision = *instruments
                .get(q.symbol.as_str())
                .context("unknown quote instrument")?;
            let bid = amount(&q.bid, precision.into(), 1_000_000, true)?;
            let ask = amount(&q.ask, precision.into(), 1_000_000, true)?;
            ensure!(bid <= ask, "crossed quote");
            ensure!(
                q.ts_ns >= global && last.get(q.symbol.as_str()).is_none_or(|t| q.ts_ns > *t),
                "quotes must be ordered, unique per instrument timestamp"
            );
            global = q.ts_ns;
            last.insert(q.symbol.as_str(), q.ts_ns);
        }
        ensure!(
            last.len() == instruments.len(),
            "every instrument needs a quote for valuation"
        );
        let mut ids = BTreeSet::new();
        for o in &self.orders {
            ensure!(
                identifier(&o.id) && ids.insert(&o.id),
                "invalid or duplicate order id"
            );
            ensure!(
                instruments.contains_key(o.symbol.as_str()),
                "unknown order instrument"
            );
            timestamp(o.information_ts_ns)?;
            amount(&o.quantity, 0, 1_000_000, true)?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct BacktestResult {
    pub schema_version: String,
    pub backend: String,
    pub backend_version: String,
    pub capabilities: Vec<String>,
    pub currency: String,
    pub cash: String,
    pub positions_value: String,
    pub equity: String,
    pub commission: String,
    pub orders: Vec<OrderResult>,
    pub fills: Vec<Fill>,
    pub positions: Vec<Position>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct OrderResult {
    pub id: String,
    pub symbol: String,
    pub status: String,
    pub filled_quantity: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Fill {
    pub order_id: String,
    pub symbol: String,
    pub side: Side,
    pub ts_ns: u64,
    pub quantity: String,
    pub price: String,
    pub commission: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Position {
    pub symbol: String,
    pub quantity: String,
    pub mark_price: String,
    pub market_value: String,
}
