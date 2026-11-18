import en from "../locales/diagrams/en.json" with { type: "json" };
import zh from "../locales/diagrams/zh-CN.json" with { type: "json" };
export type DiagramKey = keyof typeof en;
export function diagramText(
  locale: string,
  key: DiagramKey,
  values: Record<string, string> = {},
) {
  const text = (locale === "zh-CN" ? zh : en)[key] ?? en[key];
  return text.replace(/\{(\w+)\}/g, (_, name: string) => values[name] ?? "");
}
