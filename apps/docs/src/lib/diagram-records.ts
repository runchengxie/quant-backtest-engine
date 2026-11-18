import type { Event, LearningTrace } from "./trace-schema.ts";
import { diagramText } from "./diagram-catalog.ts";

export function alignedPathRecord(
  trace: LearningTrace,
  event: Event,
  other: LearningTrace,
): Event | null {
  if (
    trace.scene_id !== "paths" ||
    other.scene_id !== "paths" ||
    trace.comparison?.axis !== "utc_ns_stage" ||
    trace.currency !== other.currency ||
    trace.units.money !== other.units.money
  )
    return null;
  const point = trace.comparison?.points.find((p) => p.id === event.event_id);
  const id = point?.events[other.preset_id];
  const candidate = id ? other.events.find((e) => e.event_id === id) : null;
  if (
    !candidate ||
    candidate.stage !== event.stage ||
    candidate.clock.kind !== event.clock.kind ||
    candidate.clock.value !== event.clock.value ||
    candidate.clock.timezone !== event.clock.timezone
  )
    return null;
  return candidate;
}

export function recordClock(
  event: Event,
  locale: string,
  compact = false,
): string {
  const value = event.clock.value;
  if (event.clock.kind === "utc_ns") {
    try {
      if (!/^\d+$/.test(value)) return diagramText(locale, "unknown");
      const nanos = BigInt(value);
      const time = new Date(Number(nanos / 1000000n));
      const clock = new Intl.DateTimeFormat(
        locale === "zh-CN" ? "zh-CN" : "en-GB",
        {
          timeZone: "Asia/Shanghai",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hourCycle: "h23",
        },
      ).format(time);
      const fraction = (nanos % 1000000000n)
        .toString()
        .padStart(9, "0")
        .replace(/0+$/, "");
      const precise = clock + (fraction ? "." + fraction : "");
      return compact
        ? precise
        : precise + " · " + diagramText(locale, "time.utc");
    } catch {
      return diagramText(locale, "unknown");
    }
  }
  if (event.clock.kind === "iso_datetime") {
    try {
      const formatted = new Intl.DateTimeFormat(
        locale === "zh-CN" ? "zh-CN" : "en-GB",
        {
          timeZone: "Asia/Shanghai",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23",
        },
      ).format(new Date(value));
      return formatted + " · " + diagramText(locale, "time.utc");
    } catch {
      return diagramText(locale, "unknown");
    }
  }
  if (event.clock.kind === "elapsed_ms")
    return diagramText(locale, "time.ms", { value });
  if (event.clock.kind === "elapsed_s")
    return diagramText(locale, "time.s", { value });
  if (event.clock.kind === "trial_index")
    return diagramText(locale, "time.trial", {
      value: String(event.values.trial ?? value),
    });
  if (event.clock.kind === "event_index")
    return diagramText(locale, "time.index", { value });
  return value;
}

export function recordMoneyUnit(trace: LearningTrace, locale: string): string {
  return /^[A-Z]{3}$/.test(trace.units.money ?? "")
    ? trace.units.money
    : diagramText(locale, "unit.synthetic");
}
