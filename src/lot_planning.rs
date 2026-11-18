//! Exact finite buy-only lot planning; no execution or account mutation.
use anyhow::{Result, ensure};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::str::FromStr;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LotRequest {
    pub schema_version: String,
    pub prices: Vec<String>,
    pub target_quantities: Vec<String>,
    pub max_lots: Vec<u64>,
    pub lot_sizes: Vec<u64>,
    pub cash_budget: String,
    pub minimum_commission: String,
    pub proportional_commission: String,
    pub max_states: u64,
    pub candidate_quantities: Option<Vec<u64>>,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LotResult {
    pub schema_version: String,
    pub request_sha256: String,
    pub status: String,
    pub quantities: Option<Vec<u64>>,
    pub objective: Option<String>,
    pub spent: Option<String>,
    pub evaluated: u64,
    pub domain_states: Option<u64>,
    pub candidate_status: String,
    pub candidate_gap: Option<String>,
}
fn amount(s: &str, maximum: u64, positive: bool) -> Result<Decimal> {
    let parts = s.split('.').collect::<Vec<_>>();
    ensure!(
        parts.len() <= 2 && !parts[0].is_empty(),
        "decimal string required"
    );
    ensure!(
        parts[0] == "0" || !parts[0].starts_with('0'),
        "canonical decimal required"
    );
    ensure!(
        parts
            .iter()
            .all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit())),
        "nonnegative decimal required"
    );
    ensure!(
        parts.len() == 1 || parts[1].len() <= 4,
        "at most four decimal places supported"
    );
    let v = Decimal::from_str(s)?;
    ensure!(
        v <= Decimal::from(maximum) && (!positive || v > Decimal::ZERO),
        "amount outside supported range"
    );
    Ok(v)
}
struct Domain {
    prices: Vec<Decimal>,
    targets: Vec<Decimal>,
    budget: Decimal,
    minimum: Decimal,
    rate: Decimal,
}
impl LotRequest {
    fn domain(&self) -> Result<Domain> {
        ensure!(
            self.schema_version == "engine_lot_request.v1",
            "unsupported lot schema"
        );
        let n = self.prices.len();
        ensure!(
            (1..=16).contains(&n)
                && [
                    self.target_quantities.len(),
                    self.max_lots.len(),
                    self.lot_sizes.len()
                ]
                .iter()
                .all(|v| *v == n),
            "1..16 aligned assets required"
        );
        ensure!(
            (1..=100_000).contains(&self.max_states),
            "max_states must be 1..100000"
        );
        for (bound, lot) in self.max_lots.iter().zip(&self.lot_sizes) {
            ensure!(
                *lot > 0
                    && *lot <= 1_000_000_000
                    && bound.checked_mul(*lot).is_some_and(|q| q <= 1_000_000_000),
                "quantity bound exceeded"
            );
        }
        Ok(Domain {
            prices: self
                .prices
                .iter()
                .map(|s| amount(s, 1_000_000, true))
                .collect::<Result<_>>()?,
            targets: self
                .target_quantities
                .iter()
                .map(|s| amount(s, 1_000_000_000, false))
                .collect::<Result<_>>()?,
            budget: amount(&self.cash_budget, 1_000_000_000_000, false)?,
            minimum: amount(&self.minimum_commission, 1_000_000, false)?,
            rate: amount(&self.proportional_commission, 1, false)?,
        })
    }
    pub fn request_digest(&self) -> Result<String> {
        Ok(
            Sha256::digest(serde_json::to_vec(&serde_json::to_value(self)?)?)
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect(),
        )
    }
}
fn evaluate(d: &Domain, q: &[u64]) -> Result<(Decimal, Decimal)> {
    let mut spent = Decimal::ZERO;
    let mut loss = Decimal::ZERO;
    for ((price, target), qty) in d.prices.iter().zip(&d.targets).zip(q) {
        let quantity = Decimal::from(*qty);
        let notional = price
            .checked_mul(quantity)
            .ok_or_else(|| anyhow::anyhow!("notional overflow"))?;
        let fee = if *qty == 0 {
            Decimal::ZERO
        } else {
            d.minimum.max(
                d.rate
                    .checked_mul(notional)
                    .ok_or_else(|| anyhow::anyhow!("fee overflow"))?,
            )
        };
        spent = spent
            .checked_add(notional + fee)
            .ok_or_else(|| anyhow::anyhow!("budget overflow"))?;
        let error = quantity - *target;
        loss = loss
            .checked_add(
                error
                    .checked_mul(error)
                    .ok_or_else(|| anyhow::anyhow!("objective overflow"))?,
            )
            .ok_or_else(|| anyhow::anyhow!("objective overflow"))?;
    }
    Ok((spent, loss))
}
/// Enumerate the declared bounded grid in lexicographic quantity order.
/// Fees are exact planning amounts without currency rounding, as in the Python oracle.
pub fn plan_lots(r: &LotRequest) -> Result<LotResult> {
    let d = r.domain()?;
    let states = r
        .max_lots
        .iter()
        .try_fold(1_u64, |a, b| a.checked_mul(b + 1));
    let mut result = LotResult {
        schema_version: "engine_lot_result.v1".into(),
        request_sha256: r.request_digest()?,
        status: "search_limit".into(),
        quantities: None,
        objective: None,
        spent: None,
        evaluated: 0,
        domain_states: states,
        candidate_status: "not_provided".into(),
        candidate_gap: None,
    };
    let Some(states) = states.filter(|s| *s <= r.max_states) else {
        return Ok(result);
    };
    let mut best: Option<(Decimal, Vec<u64>, Decimal)> = None;
    for index in 0..states {
        let mut cursor = index;
        let mut quantities = vec![0; r.prices.len()];
        for i in (0..quantities.len()).rev() {
            quantities[i] = (cursor % (r.max_lots[i] + 1)) * r.lot_sizes[i];
            cursor /= r.max_lots[i] + 1;
        }
        let (spent, loss) = evaluate(&d, &quantities)?;
        if spent <= d.budget && best.as_ref().is_none_or(|b| loss < b.0) {
            best = Some((loss, quantities, spent));
        }
    }
    let (loss, quantities, spent) =
        best.expect("validated nonnegative budget admits the zero plan");
    if let Some(q) = &r.candidate_quantities {
        result.candidate_status = "infeasible".into();
        if q.len() == r.prices.len()
            && q.iter()
                .zip(&r.max_lots)
                .zip(&r.lot_sizes)
                .all(|((q, b), s)| *q <= b * s && q % s == 0)
        {
            let (cost, candidate_loss) = evaluate(&d, q)?;
            if cost <= d.budget {
                result.candidate_status = "feasible".into();
                result.candidate_gap = Some((candidate_loss - loss).normalize().to_string());
            }
        }
    }
    result.status = "optimal_exhaustive".into();
    result.quantities = Some(quantities);
    result.objective = Some(loss.normalize().to_string());
    result.spent = Some(spent.normalize().to_string());
    result.evaluated = states;
    Ok(result)
}
