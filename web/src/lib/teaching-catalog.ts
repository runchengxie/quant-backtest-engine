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
  "opportunity.title": "Calculate a separate missed opportunity",
  "opportunity.note":
    "A separate prepared order requests 200 shares. It fills 100 at 10.1 against reference price 10, with recorded fees of 5. Choose an assumed end price for this counterfactual example. It is separate from the replay and carries no market probability.",
  "opportunity.end": "Assumed end price",
  "opportunity.executed": "Executed reference cost including recorded fees",
  "opportunity.unfilled": "Unfilled opportunity gain or loss",
  "opportunity.interpret":
    "A positive unfilled value measures missed gains. A negative value measures losses avoided by leaving shares unfilled. The executed cost uses a separate comparison. Read these two recorded outputs separately and retain the recorded account cash.",
  "opportunity.provenance": "Example source and data receipt",
  "opportunity.hash": "Payload SHA-256",
  "opportunity.api": "Financial owner API",
  "opportunity.revision": "Provider revision",
  "opportunity.wheel": "Owner wheel SHA-256",
  "opportunity.source": "Source SHA-256",
  "opportunity.limit":
    "These synthetic inputs are asserted by the caller. Real-market calibration is unavailable.",
  evidence: "Check numbers and evidence",
  map: "How the stages connect",
  "flow.visual": "Follow orders through fills to actual holdings",
  "selection.title": "Six trials, one selected result",
  "selection.note":
    "The highest recorded score is selected from six trials with null covariance zero. This shows selection on the same sample. Searching candidates can select a positive result without a forecasting signal. The trials have no assigned outcome probabilities.",
  "risk.title": "Compare the forecast with what was observed",
  "risk.note":
    "Check forecasts against matching outcomes. Missing observations stay unknown. A small or incomplete synthetic sample cannot establish calibration. Marked wealth includes holdings valued at recorded prices. Cash-realized wealth requires realization.",
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
    "Follow the stages from prediction to the next decision. Stages without a recorded field remain unknown. This supplied-order example records no forecast model or optimizer run.",
  "flow.forecast": "Prediction",
  "flow.target": "Portfolio target",
  "flow.order": "Order",
  "flow.execution": "Execution",
  "flow.account": "Account",
  "flow.replan": "Replan",
  "flow.forecast.note":
    "A return forecast supplies input for choosing a target.",
  "flow.target.note":
    "Choose targets within the portfolio budget and joint constraints.",
  "flow.order.note":
    "Inspect whether the order is pending, rejected or partly filled.",
  "flow.execution.note": "Only recorded executions change traded inventory.",
  "flow.account.note":
    "Use current cash and actual holdings for the next decision.",
  "flow.replan.note":
    "Use updated account state and outstanding orders. Keep a missing target unknown.",
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
  "book.title": "Read fills and the later report",
  "book.note":
    "Compare cumulative fills, unfilled shares and reported shares on the same scale. The price ladder lists recorded execution prices. The live order book remains unavailable. Equal clocks can contain separate ordered events.",
  "book.report":
    "The later report confirms the existing fill. Account holdings stay as recorded.",
  "impact.title": "Compare impact and recovery assumptions",
  "impact.note":
    "The solid teal curve shows transient displacement. The dashed orange curve shows permanent displacement. Points use event order on the horizontal axis and a common vertical scale. Horizontal spacing carries no elapsed-time meaning. Read the fill or mark offset separately under its recorded pricing convention. Summing states would introduce a new pricing rule. Permanent impact persists by model assumption. Real-market persistence remains unverified.",
  transient: "Transient displacement",
  permanent: "Permanent displacement",
  offset: "Fill / mark offset",
  unaffected: "Unaffected price",
  "lots.title": "Compare the whole-share choices",
  "lots.note":
    "Each square is a recorded share pair. Color shows recorded feasibility and the outline marks the current event’s portfolio. Read the integer choices directly. Fractional shares are outside the domain. This finite search provides no continuous global-optimality certificate or HJB solution.",
  feasible: "Feasible",
  infeasible: "Infeasible",
  shares: "Share pair",
  "paths.title": "Compare each account separately",
  "paths.note":
    "These deterministic scenarios have no assigned probabilities. Select events in the active path and compare the other accounts at matching events. Each path retains its own event IDs and account records. Missing matches stay missing.",
  "cost.title": "Check cash debits and missed opportunity",
  "cost.note":
    "Opportunity cost compares a specified benchmark with the achieved outcome. Unfilled shares can miss a rise or avoid a fall. Specify the benchmark, horizon and unfilled amount before calculating. Account fees and cash retain the recorded ledger values. Missed gains create no further debit.",
  "cost.formula":
    "Opportunity difference equals benchmark outcome minus achieved outcome. Account cash retains its recorded debits.",
  "method.note":
    "This map explains public modeling ideas and the method recalled by the user. Authenticity and reproduction of unpublished proprietary algorithms remain unverified.",
};
const zh: typeof en = {
  "opportunity.title": "计算另一个未成交机会的得失",
  "opportunity.note":
    "这个独立预设买单要求买入 200 股，其中 100 股以 10.1 成交，参考价为 10，记录费用为 5。选择假设期末价格，计算反事实结果。这个例子独立于当前回放，没有附带市场概率。",
  "opportunity.end": "假设期末价格",
  "opportunity.executed": "已成交部分相对参考价的成本（含记录费用）",
  "opportunity.unfilled": "未成交部分的机会得失",
  "opportunity.interpret":
    "未成交值为正，表示错过收益。为负时，表示未成交部分避开亏损。已成交成本另有比较口径。分别读取这两个结果，账户现金沿用原有记录。",
  "opportunity.provenance": "示例来源与数据校验",
  "opportunity.hash": "数据 SHA-256",
  "opportunity.api": "财务计算 API",
  "opportunity.revision": "计算方版本",
  "opportunity.wheel": "计算方安装包 SHA-256",
  "opportunity.source": "来源 SHA-256",
  "opportunity.limit": "这些合成输入由调用方声明，真实市场校准仍缺少证据。",
  evidence: "核对数值与证据",
  map: "各阶段如何相连",
  "flow.visual": "跟着订单查看成交与实际持仓",
  "selection.title": "六次尝试，一个入选结果",
  "selection.note":
    "这六次尝试的零假设协方差为零，记录中得分最高的一次被选中。这个例子展示同样本选择的结果。缺少预测信号时，搜索候选仍能选出正收益。各次尝试没有附带结果概率。",
  "risk.title": "把预测与实际观察放在一起看",
  "risk.note":
    "先把预测与对应的实际结果配对，缺失观测保留未知。小规模或不完整的合成样本无法验证校准情况。账户估值包含按记录价格计算的持仓价值，完全变现后的金额需要实际变现记录。",
  predicted_variance: "预测方差",
  realized_squared_residual: "实际残差平方",
  wealth: "账户估值",
  cash_realized_wealth: "完全变现金额",
  score: "得分",
  trial: "尝试",
  selected: "入选",
  gross: "已记录成交款",
  impact_cost: "价格内已含冲击",

  "flow.title": "从预测到下一次决策",
  "flow.note":
    "按顺序查看从预测到下一次决策的各阶段。缺少记录字段的阶段保留未知。本例直接给定订单，没有记录预测模型或优化器的运行。",
  "flow.forecast": "预测",
  "flow.target": "组合目标",
  "flow.order": "订单",
  "flow.execution": "成交",
  "flow.account": "账户",
  "flow.replan": "重新规划",
  "flow.forecast.note": "收益预测为选择目标提供输入。",
  "flow.target.note": "选择目标时，要同时满足组合预算和各项约束。",
  "flow.order.note": "查看订单的等待、拒绝或部分成交状态。",
  "flow.execution.note": "只有已记录的成交才改变交易持仓。",
  "flow.account.note": "下一次决策使用当前现金与实际持仓。",
  "flow.replan.note":
    "根据更新后的账户与未完成订单再决策。缺失目标保留未知。",
  unknown: "未记录",
  value: "记录值",
  event: "事件",
  price: "价格",
  quantity: "实际／已成交股数",
  remaining: "未成交股数",
  reported: "已报告股数",
  cash: "现金",
  next_target: "下一目标",
  pending: "有待处理订单",
  fees: "费用",
  true: "是",
  false: "否",
  "book.title": "查看成交与后续报告",
  "book.note":
    "在同一股数尺度上比较累计成交、未成交与已报告数量。下方阶梯列出已记录的成交价格，实时订单簿仍缺少记录。同一时刻可以包含多个有先后顺序的事件。",
  "book.report": "后续报告确认已有成交，实际持仓沿用成交记录。",
  "impact.title": "比较冲击与恢复假设",
  "impact.note":
    "青色实线表示暂时冲击，橙色虚线表示永久冲击。各点按事件顺序排列，纵向使用同一尺度。横向间距没有实际时间含义。成交或估值偏移采用记录中的定价约定，需单独读取。把状态相加会引入另一套定价规则。永久项持续存在来自模型假设，真实市场的持续性仍未验证。",
  transient: "暂时冲击位移",
  permanent: "永久冲击位移",
  offset: "成交／估值偏移",
  unaffected: "无冲击价格",
  "lots.title": "比较整股组合",
  "lots.note":
    "每格是一对已记录的持股数量。颜色表示可行性，外框标出当前事件的组合。直接查看整数选择，小数股超出本次范围。这次有限搜索未证明连续问题的全局最优，也未给出 HJB 方程的解。",
  feasible: "可行",
  infeasible: "不可行",
  shares: "两种资产的股数",
  "paths.title": "分别查看各路径的账户",
  "paths.note":
    "这些确定性情景没有附带概率。选择当前路径的事件，在对应事件上比较其他账户。各路径保留自己的事件标识和账户记录，缺少对应事件时保留缺失。",
  "cost.title": "核对现金扣款与机会得失",
  "cost.note":
    "机会成本比较指定基准与实际结果。未成交部分可能错过上涨，也可能避开下跌。计算前先明确基准、期限和未成交数量。账户费用与现金沿用已记录的账本值，错过的收益无需再次扣款。",
  "cost.formula": "机会差额等于基准结果减去实际结果。账户现金沿用已记录的扣款。",
  "method.note":
    "这张图介绍公开建模思路和用户回忆的方法。未公开专有算法的真实性与复现情况仍无从核验。",
};
export type TeachingKey = keyof typeof en;
export function teachingText(locale: string, key: TeachingKey): string {
  return (locale === "zh-CN" ? zh[key] : undefined) ?? en[key];
}
