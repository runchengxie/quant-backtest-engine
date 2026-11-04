//! Explicit-session, raw-price execution contract; independent from the v1 wire schema.
use crate::contract::{Fill, OrderIntent, OrderResult};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SessionRequest {
    pub schema_version: String,
    pub currency: String,
    pub price_basis: String,
    pub initial_cash: String,
    pub fee_bps: String,
    pub enforce_t1: bool,
    pub instruments: Vec<SessionInstrument>,
    pub sessions: Vec<MarketSession>,
    pub required_capabilities: Vec<String>,
}
/// Library configuration for owned whole-session input; contains no session payload.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SessionConfig {
    pub schema_version: String,
    pub currency: String,
    pub price_basis: String,
    pub initial_cash: String,
    pub fee_bps: String,
    pub enforce_t1: bool,
    pub instruments: Vec<SessionInstrument>,
    pub required_capabilities: Vec<String>,
}
impl From<&SessionRequest> for SessionConfig {
    fn from(request: &SessionRequest) -> Self {
        Self {
            schema_version: request.schema_version.clone(),
            currency: request.currency.clone(),
            price_basis: request.price_basis.clone(),
            initial_cash: request.initial_cash.clone(),
            fee_bps: request.fee_bps.clone(),
            enforce_t1: request.enforce_t1,
            instruments: request.instruments.clone(),
            required_capabilities: request.required_capabilities.clone(),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SessionInstrument {
    pub symbol: String,
    pub price_precision: u8,
    pub buy_lot: u32,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct MarketSession {
    pub session_date: String,
    pub open_ts_ns: u64,
    pub valuation_ts_ns: u64,
    pub quotes: Vec<SessionQuote>,
    pub orders: Vec<OrderIntent>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SessionQuote {
    pub symbol: String,
    pub ts_ns: u64,
    pub bid: String,
    pub ask: String,
    pub bid_size: String,
    pub ask_size: String,
    pub tradable: bool,
    pub limit_up: bool,
    pub limit_down: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct SessionResult {
    pub initial_cash: String,
    pub rejections: Vec<Rejection>,
    pub enforce_t1: bool,
    pub price_basis: String,
    pub valuation_timezone: String,
    pub schema_version: String,
    pub backend: String,
    pub backend_version: String,
    pub currency: String,
    pub capabilities: Vec<String>,
    pub final_cash: String,
    pub final_nav: String,
    pub total_commission: String,
    pub orders: Vec<OrderResult>,
    pub fills: Vec<Fill>,
    pub daily_ledger: Vec<DailyBalance>,
    pub daily_positions: Vec<DailyPosition>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct DailyBalance {
    pub session_date: String,
    pub valuation_ts_ns: u64,
    pub cash: String,
    pub positions_value: String,
    pub nav: String,
    pub commission: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct DailyPosition {
    pub session_date: String,
    pub symbol: String,
    pub quantity: String,
    pub mark_price: String,
    pub market_value: String,
}

pub const SESSION_CAPABILITIES: &[&str] = &[
    "session_ledger",
    "configured_t_plus_one",
    "buy_lots",
    "quote_trade_permissions",
    "quote_liquidity",
];

impl SessionRequest {
    pub fn validate(&self) -> anyhow::Result<()> {
        anyhow::ensure!(
            !self.sessions.is_empty(),
            "sessions and instruments are required"
        );
        let mut validation = SessionValidation::new(&SessionConfig::from(self))?;
        for session in &self.sessions {
            validation.validate(session)?;
        }
        Ok(())
    }
}
impl SessionConfig {
    pub fn validate(&self) -> anyhow::Result<()> {
        SessionValidation::new(self).map(|_| ())
    }
}
pub(crate) struct SessionValidation {
    currency: String,
    instruments: std::collections::BTreeMap<String, SessionInstrument>,
    last_date: String,
    previous_close: u64,
    ids: std::collections::BTreeSet<String>,
}
impl SessionValidation {
    pub(crate) fn new(config: &SessionConfig) -> anyhow::Result<Self> {
        config.validation_context()
    }
    pub(crate) fn validate(&mut self, session: &MarketSession) -> anyhow::Result<()> {
        use crate::contract::{amount, identifier, timestamp};
        use anyhow::{Context, ensure};
        use std::collections::BTreeMap;
        let date: jiff::civil::Date = session.session_date.parse()?;
        ensure!(
            date.to_string() == session.session_date && session.session_date > self.last_date,
            "sessions must have unique increasing ISO dates"
        );
        timestamp(session.open_ts_ns)?;
        timestamp(session.valuation_ts_ns)?;
        ensure!(
            session.open_ts_ns > self.previous_close
                && session.valuation_ts_ns >= session.open_ts_ns,
            "overlapping session boundaries"
        );
        ensure!(
            session_date(session.open_ts_ns, &self.currency)? == session.session_date
                && session_date(session.valuation_ts_ns, &self.currency)? == session.session_date,
            "session timestamps do not match declared local date"
        );
        let mut last = BTreeMap::new();
        let mut global = session.open_ts_ns;
        for q in &session.quotes {
            let instrument = self
                .instruments
                .get(q.symbol.as_str())
                .context("unknown session quote instrument")?;
            ensure!(
                q.ts_ns >= global
                    && q.ts_ns <= session.valuation_ts_ns
                    && last.get(q.symbol.as_str()).is_none_or(|t| q.ts_ns > *t),
                "unordered or duplicate session quotes"
            );
            let bid = amount(&q.bid, instrument.price_precision.into(), 1_000_000, true)?;
            let ask = amount(&q.ask, instrument.price_precision.into(), 1_000_000, true)?;
            ensure!(bid <= ask, "crossed session quote");
            amount(&q.bid_size, 0, 1_000_000, false)?;
            amount(&q.ask_size, 0, 1_000_000, false)?;
            global = q.ts_ns;
            last.insert(q.symbol.as_str(), q.ts_ns);
        }
        ensure!(
            last.len() == self.instruments.len()
                && last.values().all(|t| *t == session.valuation_ts_ns),
            "every instrument needs a fresh quote at the valuation boundary"
        );
        for o in &session.orders {
            ensure!(
                identifier(&o.id)
                    && self.ids.insert(o.id.clone())
                    && self.instruments.contains_key(o.symbol.as_str()),
                "invalid or duplicate session order"
            );
            timestamp(o.information_ts_ns)?;
            ensure!(
                o.information_ts_ns >= self.previous_close
                    && o.information_ts_ns <= session.valuation_ts_ns,
                "order information falls outside its decision window"
            );
            amount(&o.quantity, 0, 1_000_000, true)?;
        }
        self.previous_close = session.valuation_ts_ns;
        self.last_date = session.session_date.clone();
        Ok(())
    }
}
impl SessionConfig {
    fn validation_context(&self) -> anyhow::Result<SessionValidation> {
        use crate::contract::{amount, identifier};
        use anyhow::ensure;
        use std::collections::BTreeMap;
        ensure!(
            self.schema_version == "engine_request.v2" && self.price_basis == "raw",
            "v2 requires raw prices and the v2 schema"
        );
        ensure!(
            matches!(self.currency.as_str(), "CNY" | "USD"),
            "unsupported session currency"
        );
        amount(&self.initial_cash, 2, 1_000_000_000_000, true)?;
        amount(&self.fee_bps, 4, 10000, false)?;
        for c in &self.required_capabilities {
            ensure!(
                SESSION_CAPABILITIES.contains(&c.as_str()),
                "unsupported session capability: {c}"
            );
        }
        ensure!(
            !self.instruments.is_empty(),
            "sessions and instruments are required"
        );
        let mut instruments = BTreeMap::new();
        for i in &self.instruments {
            ensure!(
                identifier(&i.symbol)
                    && i.price_precision <= 4
                    && i.buy_lot > 0
                    && i.buy_lot <= 1_000_000,
                "invalid session instrument"
            );
            ensure!(
                instruments.insert(i.symbol.clone(), i.clone()).is_none(),
                "duplicate session instrument"
            );
        }
        Ok(SessionValidation {
            currency: self.currency.clone(),
            instruments,
            last_date: String::new(),
            previous_close: 0,
            ids: Default::default(),
        })
    }
}

pub(crate) fn session_date(ts: u64, currency: &str) -> anyhow::Result<String> {
    let zone = if currency == "CNY" {
        jiff::tz::TimeZone::get("Asia/Shanghai")?
    } else {
        jiff::tz::TimeZone::UTC
    };
    Ok(jiff::Timestamp::from_nanosecond(ts.into())?
        .to_zoned(zone)
        .date()
        .to_string())
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Rejection {
    pub order_id: String,
    pub reason: String,
    pub event_type: String,
}
