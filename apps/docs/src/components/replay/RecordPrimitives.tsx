import type { Event, Scalar } from "../../lib/trace-schema";
import { geometryValue } from "../../lib/teaching-catalog";
import { motionText, type MotionKey } from "../../lib/motion-catalog";
import { diagramText } from "../../lib/diagram-catalog";

export function formatRecord(
  value: Scalar | undefined,
  locale: string,
  percent = false,
): string {
  if (value == null) return diagramText(locale, "unknown");
  if (typeof value === "boolean")
    return motionText(locale, value ? "yes" : "no");
  const n = geometryValue(value);
  if (n === null) {
    if (/^\d+,\d+$/.test(value)) {
      const [a, b] = value.split(",");
      return motionText(locale, "grid.pair", { a, b });
    }
    return value;
  }
  return new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en", {
    maximumFractionDigits: 4,
    ...(percent
      ? { style: "percent" as const }
      : n !== 0 && Math.abs(n) < 0.0001
        ? { notation: "scientific" as const }
        : {}),
  }).format(n);
}
export function RecordNumber({
  value,
  locale,
  percent = false,
}: {
  value: Scalar | undefined;
  locale: string;
  percent?: boolean;
}) {
  return (
    <strong
      data-value={value == null ? "" : String(value)}
      title={value == null ? diagramText(locale, "unknown") : String(value)}
    >
      {formatRecord(value, locale, percent)}
    </strong>
  );
}
export function RecordValues({
  keys,
  event,
  previous,
  locale,
  className = "",
}: {
  keys: MotionKey[];
  event: Event | null;
  previous?: Event;
  locale: string;
  className?: string;
}) {
  return (
    <dl className={"motion-values " + className}>
      {keys.map((key) => {
        const current = event?.values[key],
          old = previous?.values[key];
        const changed = old != null && current != null && old !== current;
        return (
          <div key={key} data-field={key} data-changed={changed}>
            <dt>
              {key === "next_target"
                ? diagramText(locale, "next_target")
                : motionText(locale, key)}
            </dt>
            <dd>
              {changed && (
                <span
                  className="record-previous"
                  title={diagramText(locale, "previous")}
                >
                  {formatRecord(old, locale, key === "next_target")}{" "}
                  <span aria-hidden="true">→</span>{" "}
                </span>
              )}
              <RecordNumber
                value={current}
                locale={locale}
                percent={key === "next_target"}
              />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
export function RecordBars({
  keys,
  event,
  events,
  locale,
  maximum,
}: {
  keys: MotionKey[];
  event: Event;
  events: Event[];
  locale: string;
  maximum?: number;
}) {
  const max =
    maximum ??
    Math.max(
      1e-12,
      ...events.flatMap((e) =>
        keys.map((k) => Math.abs(geometryValue(e.values[k]) ?? 0)),
      ),
    );
  return (
    <div className="teaching-bars motion-bars">
      {keys.map((key) => {
        const n = geometryValue(event.values[key]);
        return (
          <div key={key} data-field={key}>
            <span>{motionText(locale, key)}</span>
            <div className="motion-track">
              {n !== null && (
                <span
                  className="motion-bar"
                  style={{
                    width: `${Math.min(100, (Math.abs(n) / max) * 100)}%`,
                  }}
                />
              )}
            </div>
            <RecordNumber value={event.values[key]} locale={locale} />
          </div>
        );
      })}
    </div>
  );
}
