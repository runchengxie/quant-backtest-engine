export const base = "/quant-backtest-engine/";
export const scenes = [
  "flow",
  "book",
  "impact",
  "cost",
  "lots",
  "paths",
  "selection",
  "risk",
];
export function route(area: string, locale: string, scene = "") {
  return (
    base +
    area +
    "/" +
    (locale === "zh-CN" ? "zh-CN/" : "") +
    (scene ? scene + "/" : "")
  );
}
export function home(locale: string) {
  return base + (locale === "zh-CN" ? "index.zh-CN/" : "");
}
