// Geometry is a lossy display projection only. Exact financial values remain strings.
export function geometryValue(value: unknown): number | null {
  if (
    typeof value !== "string" ||
    !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value)
  )
    return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
export function relativeWidth(value: unknown, maximum: number): number | null {
  const n = geometryValue(value);
  return n === null || maximum <= 0
    ? null
    : Math.min(100, Math.max(0, (n / maximum) * 100));
}
export function signedGeometry(
  value: unknown,
  maximum: number,
): { x: number; width: number } | null {
  const n = geometryValue(value);
  if (n === null || maximum <= 0) return null;
  const width = Math.min(50, (Math.abs(n) / maximum) * 50);
  return { x: n < 0 ? 50 - width : 50, width };
}
const en = {
  "opportunity.title": "Try a separate missed-opportunity example",
  "opportunity.note":
    "A separate prepared buy order requests 200 shares; 100 fill at 10.1 against reference 10, with recorded fees 5. Choose an assumed end price. These cases are counterfactual examples, not replay events or market probabilities.",
  "opportunity.end": "Assumed end price",
  "opportunity.executed": "Executed reference cost including recorded fees",
  "opportunity.unfilled": "Unfilled opportunity — not a cash fee",
  "opportunity.interpret":
    "A positive unfilled value means a missed gain; a negative value means the unfilled shares avoided a loss. The executed cost is a separate comparison. The browser displays both owner outputs without adding them or debiting cash.",
  "opportunity.provenance": "Example source and data receipt",
  "opportunity.hash": "Payload SHA-256",
  "opportunity.api": "Financial owner API",
  "opportunity.revision": "Provider revision",
  "opportunity.wheel": "Owner wheel SHA-256",
  "opportunity.source": "Source SHA-256",
  "opportunity.limit":
    "Synthetic, caller-asserted inputs; real-market calibration is unavailable.",
  evidence: "Check numbers and evidence",
  map: "How the stages connect",
  "flow.visual": "An order becomes a holding only when it fills",
  "selection.title": "Six trials, one selected result",
  "selection.note":
    "The highest observed score was selected from these six trials. Searching more candidates can find a flattering result even when the recorded null covariance is zero. No trial is an independent probability.",
  "risk.title": "Compare the forecast with what was observed",
  "risk.note":
    "Missing observations stay blank. A small or incomplete synthetic sample cannot establish calibration; cash and marked wealth are different quantities.",
  predicted_variance: "Predicted variance",
  realized_squared_residual: "Observed squared residual",
  wealth: "Marked wealth",
  cash_realized_wealth: "Cash-realized wealth",
  score: "Score",
  trial: "Trial",
  selected: "Selected",
  gross: "Recorded gross amount",
  impact_cost: "Impact already in price",

  "flow.title": "From a forecast to the next decision",
  "flow.note":
    "This is a conceptual map. A node with no recorded field remains unknown; an arrow does not claim that this example ran an optimizer or a forecast model.",
  "flow.forecast": "Prediction",
  "flow.target": "Portfolio target",
  "flow.order": "Order",
  "flow.execution": "Execution",
  "flow.account": "Account",
  "flow.replan": "Replan",
  "flow.forecast.note":
    "A view of future returns is an input, not an executed holding.",
  "flow.target.note":
    "Targets must respect the portfolio budget and joint constraints.",
  "flow.order.note":
    "An instruction can remain pending, be rejected, or fill only partly.",
  "flow.execution.note": "Only recorded executions change traded inventory.",
  "flow.account.note":
    "Cash and actual holdings are the starting state for the next decision.",
  "flow.replan.note":
    "Use the new account and outstanding orders; a missing target is not a zero target.",
  unknown: "Not recorded",
  value: "Recorded value",
  event: "Event",
  price: "Price",
  quantity: "Actual / filled shares",
  remaining: "Unfilled shares",
  reported: "Reported shares",
  cash: "Cash",
  next_target: "Next target",
  pending: "Pending order",
  fees: "Fees",
  true: "Yes",
  false: "No",
  "book.title": "Execution and reporting are different events",
  "book.note":
    "Bars show the recorded cumulative fill, remainder and reported fill on one share scale. The price ladder below lists observed execution prices, not a reconstructed live order book. Equal clocks can contain distinct ordered events.",
  "book.report":
    "A later report acknowledges the fill; it does not buy the shares again.",
  "impact.title": "Two impact states, two recovery assumptions",
  "impact.note":
    "The solid teal curve is transient displacement; the dashed orange curve is permanent displacement. Points follow event order, not elapsed-time spacing, on a common vertical scale. The fill/mark offset is shown separately: do not sum these states to reconstruct a fill price. Permanent impact persists by assumption, not by empirical proof.",
  transient: "Transient displacement",
  permanent: "Permanent displacement",
  offset: "Fill / mark offset",
  unaffected: "Unaffected price",
  "lots.title": "A finite landscape of whole-share portfolios",
  "lots.note":
    "Each square is one recorded share pair. Color follows the owner’s feasibility result; the outline marks the currently selected event’s portfolio. Gaps are not fractional trading opportunities. This finite search certifies neither a continuous global optimum nor an HJB solution.",
  feasible: "Feasible",
  infeasible: "Infeasible",
  shares: "Share pair",
  "paths.title": "Separate paths, separate accounts",
  "paths.note":
    "These deterministic scenarios carry no probabilities. Each lane keeps its own event IDs, cash and holdings. Click an event only in the active lane; the other lanes provide context and are never advanced by copying another account’s state.",
  "cost.title": "A missed opportunity is not a second cash fee",
  "cost.note":
    "Opportunity cost compares an explicitly chosen benchmark outcome with what was achieved. Unfilled shares can miss a favorable move, or avoid an unfavorable one. The benchmark, horizon and unfilled amount must be specified before attaching a number. These displayed fees and cash remain the owner’s recorded ledger; no missed gain is deducted again.",
  "cost.formula":
    "Conceptual comparison: benchmark outcome − achieved outcome. This is not a new account debit.",
  "method.note":
    "This learning map explains public modeling ideas and the method as recalled by the user. It does not authenticate or reproduce an unpublished proprietary algorithm.",
};
const zh: typeof en = {
  "opportunity.title": "另看一个错失机会的例子",
  "opportunity.note":
    "另一个预设买单要求买入 200 股，其中 100 股以 10.1 成交，参考价为 10，记录费用为 5。选择一个假设期末价格。这些是反事实示例，不是当前回放事件，也没有附带市场概率。",
  "opportunity.end": "假设期末价格",
  "opportunity.executed": "已成交部分相对参考价的成本（含记录费用）",
  "opportunity.unfilled": "未成交部分的机会得失（不是现金费用）",
  "opportunity.interpret":
    "未成交值为正表示错过收益，为负表示未成交部分避开了亏损。已成交成本是另一项比较。浏览器只展示计算方的两个输出，不将它们相加，也不扣减现金。",
  "opportunity.provenance": "示例来源与数据校验",
  "opportunity.hash": "数据 SHA-256",
  "opportunity.api": "财务计算 API",
  "opportunity.revision": "计算方版本",
  "opportunity.wheel": "计算方安装包 SHA-256",
  "opportunity.source": "来源 SHA-256",
  "opportunity.limit": "合成数据，输入由调用方声明；没有真实市场校准。",
  evidence: "核对数值与证据",
  map: "各阶段如何相连",
  "flow.visual": "订单成交以后，才成为实际持仓",
  "selection.title": "六次尝试，一个入选结果",
  "selection.note":
    "这六次尝试中，观察得分最高的结果被选中。即使记录的零假设协方差为零，搜索更多候选也可能找到好看的结果。每次尝试并不代表独立的发生概率。",
  "risk.title": "把预测与实际观察放在一起看",
  "risk.note":
    "缺失观测保留为空。小规模或不完整的合成样本不能证明校准可靠；现金与盯市财富也是不同的量。",
  predicted_variance: "预测方差",
  realized_squared_residual: "实际残差平方",
  wealth: "盯市财富",
  cash_realized_wealth: "现金变现财富",
  score: "得分",
  trial: "尝试",
  selected: "入选",
  gross: "已记录成交款",
  impact_cost: "价格内已含冲击",

  "flow.title": "从预测到下一次决策",
  "flow.note":
    "这是一张概念图。没有记录字段的节点保留为未知；箭头不表示本例运行了优化器或预测模型。",
  "flow.forecast": "预测",
  "flow.target": "组合目标",
  "flow.order": "订单",
  "flow.execution": "成交",
  "flow.account": "账户",
  "flow.replan": "重新规划",
  "flow.forecast.note": "对未来收益的判断是输入，还不是实际持仓。",
  "flow.target.note": "组合目标需要同时满足预算和各项约束。",
  "flow.order.note": "订单可能等待、被拒绝，或者只成交一部分。",
  "flow.execution.note": "只有已记录的成交才改变交易持仓。",
  "flow.account.note": "现金与实际持仓构成下一次决策的起点。",
  "flow.replan.note":
    "根据新账户状态和未完成订单再决策；缺少目标不等于目标为零。",
  unknown: "未记录",
  value: "记录值",
  event: "事件",
  price: "价格",
  quantity: "实际／已成交股数",
  remaining: "未成交股数",
  reported: "已回报股数",
  cash: "现金",
  next_target: "下一目标",
  pending: "有待处理订单",
  fees: "费用",
  true: "是",
  false: "否",
  "book.title": "成交与回报是不同事件",
  "book.note":
    "条形在同一股数尺度上展示已记录的累计成交、未成交和已回报数量。下方价格阶梯列出观察到的成交价格，并非重建的实时订单簿。同一时刻可以包含多个有先后顺序的事件。",
  "book.report": "后续回报确认已有成交，不会再买一次。",
  "impact.title": "两种冲击状态，两种恢复假设",
  "impact.note":
    "青色实线表示暂时冲击，橙色虚线表示永久冲击。各点按事件顺序排列，横向间距不代表实际时间，纵向使用共同尺度。成交或盯市偏移单独展示，不应把这些状态相加来重算成交价。永久冲击的持续性来自假设，并非实证结论。",
  transient: "暂时冲击位移",
  permanent: "永久冲击位移",
  offset: "成交／盯市偏移",
  unaffected: "无冲击价格",
  "lots.title": "整股组合的有限可行域",
  "lots.note":
    "每个方格对应一组已记录的持股数量。颜色取自计算方的可行性结果，外框标出当前事件的组合。格点之间的空隙并不是可交易的小数股。本次有限搜索不能证明连续问题的全局最优，也不是 HJB 方程的解。",
  feasible: "可行",
  infeasible: "不可行",
  shares: "持股数量对",
  "paths.title": "各条路径，各自记账",
  "paths.note":
    "这些确定性情景没有附带概率。每条轨道保留自己的事件标识、现金与持仓。只能点击当前情景的事件；其余轨道提供对照，不会复制其他账户的状态来向前推进。",
  "cost.title": "错过的机会不是第二笔现金费用",
  "cost.note":
    "机会成本比较明确选定的基准结果与实际结果。未成交部分可能错过上涨，也可能避开下跌。给出数值前，必须明确基准、期限与未成交数量。这里的费用和现金仍是计算方的账本记录，不会再次扣除错过的收益。",
  "cost.formula": "概念比较：基准结果 − 实际结果。这不是新增的账户扣款。",
  "method.note":
    "这张学习图解释公开建模思路和用户回忆的方法，不代表对未公开专有算法的认证或复现。",
};
export type TeachingKey = keyof typeof en;
export function teachingText(locale: string, key: TeachingKey): string {
  return (locale === "zh-CN" ? zh[key] : undefined) ?? en[key];
}
