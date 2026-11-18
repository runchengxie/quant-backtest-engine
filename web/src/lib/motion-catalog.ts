const en = {
  unknown: "Not recorded", yes: "Yes", no: "No", cash: "Cash", quantity: "Shares", fees: "Fees", gross: "Gross amount", impact_cost: "Impact included in price", price: "Price", remaining: "Unfilled", reported: "Reported", shares: "Share combination", error: "Squared tracking error", score: "Score", trial: "Trial", selected: "Selected result", feasible: "Feasible", infeasible: "Infeasible", predicted_variance: "Predicted variance", realized_squared_residual: "Observed squared residual", wealth: "Marked wealth", cash_realized_wealth: "Cash-realized wealth", next_target: "Next target", pending: "Pending order", report_pending: "Report pending", transient: "Transient impact", permanent: "Permanent impact", offset: "Price offset", unaffected: "Unaffected price", cash_right: "Cash receivable", stock_right: "Share entitlement", capital_flow: "External capital", coverage: "Coverage", variance_ratio: "Variance ratio", order: "Order", fill: "Fill", account: "Account", ordinal: "Event order with equal spacing", scale: "Bar lengths share a zero and scale", precision: "Display values are rounded. Exact values appear below and on hover.", blocks: "Each block represents one requested share", lanes: "Each lane holds its own recorded account", "caption.flow": "{stage}. The account holds {quantity} shares and cash of {cash}.", "caption.book": "{stage}. Cumulative purchases reach {quantity} shares, with {remaining} still unfilled. The report covers {reported} shares.", "caption.cost": "{stage}. The gross payment is {gross} and fees are {fees}. The payment includes impact cost of {impact_cost}.", "caption.impact": "{stage}. Transient impact is {transient} and permanent impact is {permanent}.", "caption.lots": "{stage}. The chosen share pair is {shares}, leaving cash of {cash}.", "caption.paths": "This account holds {quantity} shares and cash of {cash}.", "caption.selection": "Trial {trial} scores {score}. The Selected column shows {selected}.", "caption.risk": "{stage}. Predicted variance is {predicted_variance} and observed squared residual is {realized_squared_residual}.", "caption.account": "{stage}. The account holds {quantity} shares and cash of {cash}.",
  "caption.flow.forecast": "The supplied order starts with cash of {cash}.",
  "caption.flow.buy": "The buy fills. The account now holds {quantity} shares.",
  "caption.flow.sell": "The sell fills. The account now holds {quantity} shares and cash of {cash}.",
  "caption.book.spread": "The order begins with {remaining} shares waiting to fill.",
  "caption.book.fill": "After this fill, cumulative purchases reach {quantity} shares, with {remaining} still unfilled.",
  "caption.book.report": "The report confirms {reported} shares. Cumulative fills remain at {quantity} shares.",
  "caption.cost.reserve": "Before execution, cash is {cash} and gross payment is {gross}.",
  "caption.cost.cash": "The gross payment is {gross} and fees are {fees}. The payment includes impact cost of {impact_cost}.",
  "caption.impact.fill": "This fill executes at {price}. Transient impact reaches {transient}.",
  "caption.impact.decay": "After waiting, transient impact is {transient}. Permanent impact remains {permanent}.",
  "snapshots": "Account records for each step",
  "grid.legend": "Each cell shows the recorded shares of A and B",
  "grid.pair": "A {a} · B {b}",
} as const;
const zh: Record<keyof typeof en, string> = {
  unknown: "未记录", yes: "是", no: "否", cash: "现金", quantity: "股数", fees: "费用", gross: "成交金额", impact_cost: "价格中已含冲击", price: "价格", remaining: "未成交股数", reported: "已报告股数", shares: "股数组合", error: "平方跟踪误差", score: "得分", trial: "尝试", selected: "选中结果", feasible: "可行", infeasible: "不可行", predicted_variance: "预测方差", realized_squared_residual: "实际残差平方", wealth: "账户估值", cash_realized_wealth: "完全变现金额", next_target: "下一目标", pending: "待处理订单", report_pending: "报告未送达", transient: "暂时冲击", permanent: "永久冲击", offset: "价格偏移", unaffected: "无冲击价格", cash_right: "应收现金", stock_right: "应收股数", capital_flow: "外部资金", coverage: "覆盖率", variance_ratio: "方差比", order: "订单", fill: "成交", account: "账户", ordinal: "横轴按事件顺序等距排列", scale: "条形共用零点和刻度", precision: "图中数值已四舍五入，下方表格和悬停处保留原值。", blocks: "每格代表订单中的一股", lanes: "每条路径使用各自记录的账户", "caption.flow": "{stage}。账户持有 {quantity} 股，现金为 {cash}。", "caption.book": "{stage}。累计买到 {quantity} 股，还有 {remaining} 股未成交。报告已确认 {reported} 股。", "caption.cost": "{stage}。成交款为 {gross}，费用为 {fees}。成交款中已包含 {impact_cost} 的冲击成本。", "caption.impact": "{stage}。暂时冲击为 {transient}，永久冲击为 {permanent}。", "caption.lots": "{stage}。选中的股数组合为 {shares}，剩余现金为 {cash}。", "caption.paths": "这个账户持有 {quantity} 股，现金为 {cash}。", "caption.selection": "第 {trial} 次尝试得分为 {score}。表中的选中栏显示{selected}。", "caption.risk": "{stage}。预测方差为 {predicted_variance}，实际残差平方为 {realized_squared_residual}。", "caption.account": "{stage}。账户持有 {quantity} 股，现金为 {cash}。",
  "caption.flow.forecast": "给定订单开始时，账户现金为 {cash}。",
  "caption.flow.buy": "买单成交后，账户持有 {quantity} 股。",
  "caption.flow.sell": "卖单成交后，账户持有 {quantity} 股，现金为 {cash}。",
  "caption.book.spread": "订单刚开始，还有 {remaining} 股等待成交。",
  "caption.book.fill": "这笔成交后，累计买到 {quantity} 股，还有 {remaining} 股未成交。",
  "caption.book.report": "报告确认 {reported} 股已成交，累计成交仍为 {quantity} 股。",
  "caption.cost.reserve": "成交前，现金为 {cash}，成交款为 {gross}。",
  "caption.cost.cash": "成交款为 {gross}，费用为 {fees}。成交款中已包含 {impact_cost} 的冲击成本。",
  "caption.impact.fill": "这笔成交价为 {price}，暂时冲击变为 {transient}。",
  "caption.impact.decay": "等待后，暂时冲击变为 {transient}，永久冲击保持 {permanent}。",
  "snapshots": "每一步的账户记录",
  "grid.legend": "每格显示 A 和 B 各自的持股数量",
  "grid.pair": "A {a} · B {b}",
};
export type MotionKey = keyof typeof en;
export function motionCaptionKey(scene: string, stage: string): MotionKey {
  const specific = `caption.${scene}.${stage}`;
  return (specific in en ? specific : `caption.${scene}`) as MotionKey;
}
export function motionText(locale: string, key: MotionKey, values: Record<string, string> = {}) {
  const text = (locale.startsWith("zh") ? zh : en)[key] ?? en[key];
  return text.replace(/\{(\w+)\}/g, (_, name: string) => values[name] ?? "");
}
