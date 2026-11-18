//! Pure portfolio quantity planning. Outputs are estimates, never execution evidence.
use crate::contract::OrderIntent;
use crate::contract::{Side, amount, identifier, timestamp};
use anyhow::{Result, ensure};
use nautilus_model::types::{Currency, Money};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SizingRequest {
    pub schema_version: String,
    pub currency: String,
    pub information_ts_ns: u64,
    pub cash: String,
    pub fee_bps: String,
    pub assets: Vec<SizingAsset>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SizingAsset {
    pub symbol: String,
    pub held_quantity: String,
    pub reference_price: String,
    pub price_ts_ns: u64,
    pub target_weight: String,
    pub buy_lot: u32,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct SizingResult {
    pub schema_version: String,
    pub currency: String,
    pub marked_equity: String,
    pub projected_cash: String,
    pub orders: Vec<OrderIntent>,
    pub targets: Vec<SizedTarget>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct SizedTarget {
    pub symbol: String,
    pub desired_quantity: String,
    pub planned_quantity: String,
}
struct Planned<'a> {
    asset: &'a SizingAsset,
    held: Decimal,
    price: Decimal,
    desired: Decimal,
    planned: Decimal,
}

fn text(value: Decimal) -> String {
    value.normalize().to_string()
}
fn money(value: Decimal, currency: Currency) -> Result<Decimal> {
    Ok(Money::from_decimal(value, currency)?.as_decimal())
}
fn cash_flow(
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
    currency: Currency,
) -> Result<(Decimal, Decimal)> {
    let notional = money(quantity * price, currency)?;
    Ok((notional, money(notional * fee, currency)?))
}

/// Creates a deterministic sell-first order plan from information already available.
/// Projected sale proceeds and cash are estimates. Execution must await/verify sells
/// and recheck actual upstream free cash; this plan never guarantees a future fill.
pub fn size_targets(request: &SizingRequest) -> Result<SizingResult> {
    ensure!(
        request.schema_version == "sizing_request.v1",
        "unsupported sizing schema"
    );
    let currency = match request.currency.as_str() {
        "USD" => Currency::USD(),
        "CNY" => Currency::CNY(),
        _ => anyhow::bail!("unsupported sizing currency"),
    };
    timestamp(request.information_ts_ns)?;
    let mut cash = amount(&request.cash, 2, 1_000_000_000_000, false)?;
    let fee = amount(&request.fee_bps, 4, 10000, false)? / Decimal::from(10000);
    ensure!(
        !request.assets.is_empty() && request.assets.len() <= 1024,
        "sizing needs 1-1024 explicit assets"
    );
    let mut symbols = BTreeSet::new();
    let mut weight_sum = Decimal::ZERO;
    let mut equity = cash;
    let mut planned = Vec::new();
    let mut assets: Vec<_> = request.assets.iter().collect();
    assets.sort_by(|a, b| a.symbol.cmp(&b.symbol));
    for asset in assets {
        ensure!(
            identifier(&asset.symbol) && symbols.insert(&asset.symbol),
            "invalid or duplicate sizing symbol"
        );
        timestamp(asset.price_ts_ns)?;
        ensure!(
            asset.price_ts_ns <= request.information_ts_ns,
            "reference price is unavailable at information time"
        );
        ensure!(
            asset.buy_lot > 0 && asset.buy_lot <= 1_000_000,
            "invalid buy lot"
        );
        let held = amount(&asset.held_quantity, 0, 1_000_000, false)?;
        let price = amount(&asset.reference_price, 4, 1_000_000, true)?;
        weight_sum += amount(&asset.target_weight, 8, 1, false)?;
        equity += held * price;
        planned.push(Planned {
            asset,
            held,
            price,
            desired: Decimal::ZERO,
            planned: held,
        });
    }
    ensure!(
        weight_sum <= Decimal::ONE,
        "long-only target weights exceed one"
    );
    for item in &mut planned {
        let lot = Decimal::from(item.asset.buy_lot);
        item.desired =
            (amount(&item.asset.target_weight, 8, 1, false)? * equity / item.price / lot).floor()
                * lot;
        ensure!(
            item.desired <= Decimal::from(1_000_000),
            "desired quantity exceeds engine order bounds"
        );
    }
    let mut orders = Vec::new();
    for (index, item) in planned.iter_mut().enumerate() {
        if item.desired >= item.held {
            continue;
        }
        let quantity = item.held - item.desired;
        let (notional, cost) = cash_flow(quantity, item.price, fee, currency)?;
        cash += notional - cost;
        item.planned = item.desired;
        orders.push(OrderIntent {
            id: format!("size-{}-{index:04}-sell", request.information_ts_ns),
            symbol: item.asset.symbol.clone(),
            information_ts_ns: request.information_ts_ns,
            side: Side::Sell,
            quantity: text(quantity),
        });
    }
    for (index, item) in planned.iter_mut().enumerate() {
        if item.desired <= item.held {
            continue;
        }
        let lot = Decimal::from(item.asset.buy_lot);
        let desired = item.desired - item.held;
        let affordable = (cash / (item.price * (Decimal::ONE + fee)) / lot).floor() * lot;
        let mut quantity = desired.min(affordable);
        // A held odd lot must not cause a fractional board-lot buy.
        quantity = (quantity / lot).floor() * lot;
        while quantity > Decimal::ZERO {
            let (notional, cost) = cash_flow(quantity, item.price, fee, currency)?;
            if notional + cost <= cash {
                break;
            }
            quantity -= lot;
        }
        if quantity == Decimal::ZERO {
            continue;
        }
        let (notional, cost) = cash_flow(quantity, item.price, fee, currency)?;
        cash -= notional + cost;
        item.planned += quantity;
        orders.push(OrderIntent {
            id: format!("size-{}-{index:04}-buy", request.information_ts_ns),
            symbol: item.asset.symbol.clone(),
            information_ts_ns: request.information_ts_ns,
            side: Side::Buy,
            quantity: text(quantity),
        });
    }
    Ok(SizingResult {
        schema_version: "sizing_result.v1".into(),
        currency: request.currency.clone(),
        marked_equity: text(equity),
        projected_cash: text(cash),
        orders,
        targets: planned
            .into_iter()
            .map(|p| SizedTarget {
                symbol: p.asset.symbol.clone(),
                desired_quantity: text(p.desired),
                planned_quantity: text(p.planned),
            })
            .collect(),
    })
}
