use std::collections::{BTreeMap, HashMap, VecDeque};

use pyo3::prelude::*;

type Trade = (String, String, i64, i64);
type Level = Option<(i64, i64)>;
type ReplayRow = (i64, i64, i64, i64, String);
type Tick = (i64, Level, Level, String);

#[derive(Clone)]
struct Order {
    id: String,
    volume: i64,
}

#[pyclass]
#[derive(Default)]
struct OrderBook {
    bids: BTreeMap<i64, VecDeque<Order>>,
    asks: BTreeMap<i64, VecDeque<Order>>,
    by_id: HashMap<String, (i64, i64)>,
}

impl OrderBook {
    fn add(&mut self, id: String, side: i64, price: i64, volume: i64) {
        if volume <= 0 {
            return;
        }
        let book = if side == 1 {
            &mut self.bids
        } else {
            &mut self.asks
        };
        book.entry(price).or_default().push_back(Order {
            id: id.clone(),
            volume,
        });
        self.by_id.insert(id, (side, price));
    }

    fn matching_price(&self, side: i64, limit: i64) -> Option<i64> {
        if side == 1 {
            self.asks
                .first_key_value()
                .and_then(|(&p, _)| (p <= limit).then_some(p))
        } else if side == -1 {
            self.bids
                .last_key_value()
                .and_then(|(&p, _)| (p >= limit).then_some(p))
        } else {
            self.bids.range(limit..).next().map(|(&p, _)| p)
        }
    }

    fn apply(&mut self, id: String, side: i64, price: i64, volume: i64) -> Option<Trade> {
        if volume <= 0 {
            return None;
        }
        let mut remaining = volume;
        let mut counterparty = String::new();
        let mut trade_price = 0;
        while let Some(p) = self.matching_price(side, price) {
            let book = if side == 1 {
                &mut self.asks
            } else {
                &mut self.bids
            };
            let queue = book.get_mut(&p).expect("matching price exists");
            while remaining > 0 {
                let Some(top) = queue.front_mut() else { break };
                let fill = top.volume.min(remaining);
                top.volume -= fill;
                remaining -= fill;
                counterparty.clone_from(&top.id);
                trade_price = p;
                if top.volume == 0 {
                    self.by_id.remove(&top.id);
                    queue.pop_front();
                }
            }
            if queue.is_empty() {
                book.remove(&p);
            }
            if remaining == 0 {
                break;
            }
        }
        if remaining > 0 {
            self.add(id.clone(), side, price, remaining);
        }
        (remaining < volume).then(|| {
            if side == 1 {
                (id, counterparty, trade_price, volume - remaining)
            } else {
                (counterparty, id, trade_price, volume - remaining)
            }
        })
    }

    fn cancel(&mut self, id: &str, volume: Option<i64>) -> bool {
        let Some(&(side, price)) = self.by_id.get(id) else {
            return false;
        };
        let book = if side == 1 {
            &mut self.bids
        } else {
            &mut self.asks
        };
        let Some(queue) = book.get_mut(&price) else {
            return false;
        };
        let Some(index) = queue.iter().position(|order| order.id == id) else {
            return false;
        };
        let remaining = queue[index].volume;
        if volume.is_some_and(|n| n <= 0 || n > remaining) {
            return false;
        }
        if let Some(n) = volume.filter(|&n| n < remaining) {
            queue[index].volume -= n;
        } else {
            queue.remove(index);
            self.by_id.remove(id);
        }
        if queue.is_empty() {
            book.remove(&price);
        }
        true
    }

    fn level(book: &BTreeMap<i64, VecDeque<Order>>, bid: bool) -> Level {
        let entry = if bid {
            book.last_key_value()
        } else {
            book.first_key_value()
        };
        entry.map(|(&price, orders)| (price, orders.iter().map(|order| order.volume).sum()))
    }

    fn replay_rows(
        &mut self,
        background: Vec<ReplayRow>,
        interventions: Vec<ReplayRow>,
    ) -> Vec<Tick> {
        let mut bg: Vec<_> = background.into_iter().enumerate().collect();
        let mut iv: Vec<_> = interventions.into_iter().enumerate().collect();
        bg.sort_by_key(|(_, row)| row.0);
        iv.sort_by_key(|(_, row)| row.0);
        let (mut bi, mut ii) = (0, 0);
        let mut ticks = Vec::with_capacity(bg.len() + iv.len());
        while bi < bg.len() || ii < iv.len() {
            let take_iv = ii < iv.len() && (bi == bg.len() || iv[ii].1 .0 <= bg[bi].1 .0);
            let (time, side, price, volume, id, source) = if take_iv {
                let (_, row) = &iv[ii];
                ii += 1;
                (row.0, row.1, row.2, row.3, row.4.clone(), "intervention")
            } else {
                let (_, row) = &bg[bi];
                bi += 1;
                let id = if row.4.is_empty() {
                    format!("BG{}", bi - 1)
                } else {
                    row.4.clone()
                };
                (row.0, row.1, row.2, row.3, id, "background")
            };
            self.apply(id, side, price, volume);
            ticks.push((
                time,
                Self::level(&self.bids, true),
                Self::level(&self.asks, false),
                source.to_owned(),
            ));
        }
        ticks
    }
}

#[pymethods]
impl OrderBook {
    #[new]
    fn new() -> Self {
        Self::default()
    }

    fn apply_order(
        &mut self,
        order_id: String,
        side: i64,
        price: i64,
        volume: i64,
    ) -> Option<Trade> {
        self.apply(order_id, side, price, volume)
    }

    #[pyo3(signature = (order_id, volume=None))]
    fn cancel_order(&mut self, order_id: &str, volume: Option<i64>) -> bool {
        self.cancel(order_id, volume)
    }

    fn has_order(&self, order_id: &str) -> bool {
        self.by_id.contains_key(order_id)
    }

    fn seed_level(&mut self, side: i64, price: i64, volume: i64, order_id: String) {
        if volume > 0 && price > 0 {
            self.add(order_id, side, price, volume);
        }
    }

    fn reduce_level(&mut self, side: i64, price: i64, volume: i64) -> bool {
        if volume <= 0 {
            return false;
        }
        let book = if side == 1 {
            &mut self.bids
        } else {
            &mut self.asks
        };
        let Some(queue) = book.get_mut(&price) else {
            return false;
        };
        let mut remaining = volume;
        while remaining > 0 {
            let Some(top) = queue.front_mut() else { break };
            let fill = top.volume.min(remaining);
            top.volume -= fill;
            remaining -= fill;
            if top.volume == 0 {
                self.by_id.remove(&top.id);
                queue.pop_front();
            }
        }
        if queue.is_empty() {
            book.remove(&price);
        }
        remaining < volume
    }

    fn best_bid(&self) -> Level {
        Self::level(&self.bids, true)
    }
    fn best_ask(&self) -> Level {
        Self::level(&self.asks, false)
    }

    fn replay(&mut self, background: Vec<ReplayRow>, interventions: Vec<ReplayRow>) -> Vec<Tick> {
        self.replay_rows(background, interventions)
    }
}

type SortRow = (i64, String, String, Option<i64>, i64);

#[pyfunction]
fn sort_event_indices(rows: Vec<SortRow>) -> Vec<usize> {
    let mut buckets: BTreeMap<i64, Vec<(usize, SortRow)>> = BTreeMap::new();
    for (index, row) in rows.into_iter().enumerate() {
        buckets.entry(row.0).or_default().push((index, row));
    }
    let mut ordered = Vec::new();
    for (_, bucket) in buckets {
        let (mut events, mut snapshots): (Vec<_>, Vec<_>) =
            bucket.into_iter().partition(|(_, row)| row.1 != "snapshot");
        let all_sequenced = !events.is_empty() && events.iter().all(|(_, row)| row.3.is_some());
        let channels: std::collections::HashSet<_> = events
            .iter()
            .filter(|(_, row)| row.3.is_some() && !row.2.is_empty())
            .map(|(_, row)| row.2.as_str())
            .collect();
        if all_sequenced && channels.len() <= 1 {
            events.sort_by_key(|(_, row)| (row.3.unwrap(), row.4));
        } else {
            events.sort_by_key(|(_, row)| row.4);
        }
        snapshots.sort_by_key(|(_, row)| row.4);
        ordered.extend(events.into_iter().chain(snapshots).map(|(index, _)| index));
    }
    ordered
}

#[pymodule]
fn _microstructure_rs(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<OrderBook>()?;
    module.add_function(wrap_pyfunction!(sort_event_indices, module)?)?;
    Ok(())
}
