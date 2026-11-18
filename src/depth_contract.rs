//! Explicit single-instrument L2 event contract; existing quote/session wires are unchanged.
use crate::contract::{Instrument, amount as bounded_amount, identifier, timestamp};
use anyhow::{Result, ensure};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

fn amount(value: &str, precision: u32, max: i64, positive: bool) -> Result<Decimal> {
    let whole = value.split('.').next().unwrap_or("");
    ensure!(
        !value.starts_with('-')
            && !value.ends_with('.')
            && (whole == "0" || (!whole.is_empty() && !whole.starts_with('0'))),
        "canonical nonnegative decimal required"
    );
    bounded_amount(value, precision, max, positive)
}

pub const DEPTH_CAPABILITIES: &[&str] = &[
    "l2_depth_events",
    "trade_events",
    "limit_orders",
    "cancel_orders",
    "command_latency",
    "account_feedback_targets",
    "final_balances",
    "proportional_fees",
];
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DepthRequest {
    pub schema_version: String,
    pub currency: String,
    pub initial_cash: String,
    pub fee_bps: String,
    pub instrument: Instrument,
    pub insert_latency_ns: u64,
    pub cancel_latency_ns: u64,
    pub end_ns: u64,
    pub events: Vec<DepthEvent>,
    pub commands: Vec<DepthCommand>,
    pub required_capabilities: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Level {
    pub price: String,
    pub quantity: String,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DepthEventKind {
    Snapshot,
    Delta,
    Trade,
}
impl DepthEventKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Snapshot => "snapshot",
            Self::Delta => "delta",
            Self::Trade => "trade",
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DepthAction {
    Buy,
    Sell,
    Cancel,
    Target,
}
impl DepthAction {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Buy => "buy",
            Self::Sell => "sell",
            Self::Cancel => "cancel",
            Self::Target => "target",
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DepthEvent {
    pub kind: DepthEventKind,
    pub ts_ns: u64,
    pub available_ns: u64,
    pub sequence: u64,
    pub bids: Vec<Level>,
    pub asks: Vec<Level>,
    pub trade_id: Option<String>,
    pub trade_price: Option<String>,
    pub trade_quantity: Option<String>,
    pub aggressor: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DepthCommand {
    pub id: String,
    pub event_sequence: u64,
    pub information_ts_ns: u64,
    pub action: DepthAction,
    pub quantity: String,
    pub limit_price: String,
    pub cancel_id: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DepthDecision {
    pub id: String,
    pub ts_ns: u64,
    pub action: String,
    pub held_quantity: String,
    pub free_cash: String,
    pub admissible_cash: String,
    pub total_cash: String,
    pub locked_cash: String,
    pub observed_fill_count: u64,
    pub working_order_ids: Vec<String>,
    pub submitted_quantity: String,
    pub outcome: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DepthReceipt {
    pub order_id: String,
    pub kind: String,
    pub ts_ns: u64,
    pub received_ns: u64,
    pub trade_id: Option<String>,
    pub fill: Option<crate::contract::Fill>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DepthResult {
    pub schema_version: String,
    pub request_sha256: String,
    pub capabilities: Vec<String>,
    pub decisions: Vec<DepthDecision>,
    pub receipts: Vec<DepthReceipt>,
    pub fill_order: Vec<String>,
    pub valuation_ns: u64,
    pub observation_ns: u64,
    pub account: crate::contract::BacktestResult,
}
impl DepthRequest {
    pub fn validate(&self) -> Result<()> {
        ensure!(
            self.schema_version == "engine_depth_request.v1",
            "unsupported depth schema"
        );
        ensure!(
            self.currency == "CNY" || self.currency == "USD",
            "unsupported currency"
        );
        amount(&self.initial_cash, 2, 1_000_000_000_000, true)?;
        amount(&self.fee_bps, 4, 1000, false)?;
        ensure!(
            identifier(&self.instrument.symbol) && self.instrument.price_precision <= 4,
            "invalid instrument"
        );
        timestamp(self.end_ns)?;
        ensure!(
            self.insert_latency_ns <= 60_000_000_000 && self.cancel_latency_ns <= 60_000_000_000,
            "latency exceeds 60 seconds"
        );
        ensure!(
            !self.events.is_empty()
                && self.events.len() <= 100_000
                && self.commands.len() <= 10_000,
            "invalid event/command budget"
        );
        ensure!(
            self.events[0].kind.as_str() == "snapshot",
            "first event must initialize the depth snapshot"
        );
        let mut trade_ids = BTreeSet::new();
        let mut last_depth_ns = 0;
        let mut depth_rows = 0_usize;
        let mut keys = BTreeMap::new();
        let mut previous = None;
        let mut bids = BTreeMap::new();
        let mut asks = BTreeMap::new();
        for e in &self.events {
            timestamp(e.ts_ns)?;
            timestamp(e.available_ns)?;
            ensure!(e.sequence > 0, "positive sequence required");
            ensure!(
                e.ts_ns == e.available_ns && e.available_ns <= self.end_ns,
                "invalid event availability"
            );
            if let Some((available, seq)) = previous {
                ensure!(
                    e.available_ns >= available && e.sequence > seq,
                    "events require arrival order and strictly increasing sequence"
                );
            }
            previous = Some((e.available_ns, e.sequence));
            keys.insert(e.sequence, e.available_ns);
            ensure!(
                e.bids.len() <= 100 && e.asks.len() <= 100,
                "depth level budget exceeded"
            );
            depth_rows += e.bids.len() + e.asks.len();
            ensure!(depth_rows <= 1_000_000, "depth row budget exceeded");
            match e.kind.as_str() {
                "snapshot" | "delta" => {
                    last_depth_ns = e.available_ns;
                    ensure!(
                        !e.bids.is_empty() || !e.asks.is_empty(),
                        "empty depth event is unsupported"
                    );
                    ensure!(
                        e.trade_id.is_none()
                            && e.trade_price.is_none()
                            && e.trade_quantity.is_none()
                            && e.aggressor.is_none(),
                        "depth event cannot carry a trade"
                    );
                    if e.kind.as_str() == "snapshot" {
                        bids.clear();
                        asks.clear();
                    }
                    for (levels, book) in [(&e.bids, &mut bids), (&e.asks, &mut asks)] {
                        let mut seen = BTreeSet::new();
                        for l in levels {
                            let p = amount(
                                &l.price,
                                self.instrument.price_precision.into(),
                                1_000_000,
                                true,
                            )?;
                            let q = amount(&l.quantity, 0, 1_000_000_000, false)?;
                            ensure!(seen.insert(p), "duplicate depth price");
                            ensure!(
                                e.kind.as_str() != "snapshot" || q > Decimal::ZERO,
                                "snapshot quantities must be positive"
                            );
                            if q == Decimal::ZERO {
                                ensure!(
                                    book.remove(&p).is_some(),
                                    "delete references an absent price level"
                                );
                            } else {
                                book.insert(p, q);
                            }
                        }
                    }
                    ensure!(
                        !bids.is_empty() && !asks.is_empty(),
                        "both book sides must remain observable"
                    );
                    ensure!(
                        bids.last_key_value().unwrap().0 < asks.first_key_value().unwrap().0,
                        "crossed/locked book is unsupported"
                    );
                }
                "trade" => {
                    ensure!(
                        e.trade_id.as_deref().is_some_and(identifier),
                        "trade identity is required"
                    );
                    ensure!(
                        trade_ids.insert(e.trade_id.as_deref().unwrap()),
                        "duplicate market trade identity"
                    );
                    ensure!(
                        e.bids.is_empty() && e.asks.is_empty(),
                        "trade event cannot carry depth"
                    );
                    amount(
                        e.trade_price.as_deref().unwrap_or(""),
                        self.instrument.price_precision.into(),
                        1_000_000,
                        true,
                    )?;
                    amount(
                        e.trade_quantity.as_deref().unwrap_or(""),
                        0,
                        1_000_000_000,
                        true,
                    )?;
                    ensure!(
                        matches!(e.aggressor.as_deref(), Some("buy" | "sell")),
                        "explicit aggressor side required"
                    );
                }
                _ => anyhow::bail!("unsupported event kind"),
            }
        }
        ensure!(
            self.end_ns - last_depth_ns <= 60_000_000_000,
            "final depth mark exceeds the 60-second age bound"
        );
        let mut ids = BTreeSet::new();
        let mut used = BTreeSet::new();
        let mut order_ids = BTreeSet::new();
        let mut previous_command = None;
        let mut buy_budget = Decimal::ZERO;
        for c in &self.commands {
            ensure!(
                identifier(&c.id) && ids.insert(c.id.as_str()),
                "duplicate/invalid command identity"
            );
            let available = *keys
                .get(&c.event_sequence)
                .ok_or_else(|| anyhow::anyhow!("unknown command event sequence"))?;
            if let Some(seq) = previous_command {
                ensure!(
                    c.event_sequence > seq,
                    "commands must follow event sequence"
                );
            }
            previous_command = Some(c.event_sequence);
            ensure!(
                used.insert(c.event_sequence),
                "one command per event is supported"
            );
            timestamp(c.information_ts_ns)?;
            ensure!(
                c.information_ts_ns < available,
                "command information must precede decision"
            );
            let latency = if c.action.as_str() == "cancel" {
                self.cancel_latency_ns
            } else {
                self.insert_latency_ns
            };
            ensure!(
                available
                    .checked_add(latency)
                    .is_some_and(|t| t < self.end_ns),
                "observation horizon must extend past command arrival"
            );
            let quantity = amount(&c.quantity, 0, 1_000_000_000, false)?;
            match c.action.as_str() {
                "buy" | "sell" | "target" => {
                    if c.action.as_str() != "sell" {
                        buy_budget += quantity;
                        ensure!(
                            buy_budget <= Decimal::from(1_000_000_000_u64),
                            "aggregate buy/target quantity budget exceeded"
                        );
                    }
                    ensure!(
                        c.cancel_id.is_none()
                            && (c.action.as_str() == "target" || quantity > Decimal::ZERO),
                        "invalid order command"
                    );
                    amount(
                        &c.limit_price,
                        self.instrument.price_precision.into(),
                        1_000_000,
                        true,
                    )?;
                    order_ids.insert(c.id.as_str());
                }
                "cancel" => {
                    ensure!(
                        quantity == Decimal::ZERO && c.limit_price == "0",
                        "cancel has no quantity or limit price"
                    );
                    ensure!(
                        c.cancel_id
                            .as_deref()
                            .is_some_and(|id| order_ids.contains(id)),
                        "cancel requires an earlier order identity"
                    );
                }
                _ => anyhow::bail!("unsupported command action"),
            }
        }
        let mut caps = BTreeSet::new();
        for cap in &self.required_capabilities {
            ensure!(
                DEPTH_CAPABILITIES.contains(&cap.as_str()) && caps.insert(cap),
                "unsupported/duplicate capability"
            );
        }
        Ok(())
    }
}

/// Canonical request bytes bind validation receipts and executed results.
pub fn request_digest(request: &DepthRequest) -> Result<String> {
    use sha2::{Digest, Sha256};
    Ok(
        Sha256::digest(serde_json::to_vec(&serde_json::to_value(request)?)?)
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect(),
    )
}
