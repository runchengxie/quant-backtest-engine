import type { Event } from "../../lib/trace-schema";
export default function TraceChart({
  event,
  events,
  t,
}: {
  event: Event;
  events: Event[];
  t: (k: string) => string;
}) {
  const fields = [
    "cash",
    "price",
    "transient",
    "permanent",
    "offset",
    "score",
    "wealth",
    "predicted_variance",
    "realized_squared_residual",
  ].filter((key) => events.some((e) => typeof e.values[key] === "string"));
  return (
    <section data-view="chart" data-event={event.event_id}>
      <h3>{t("learning.snapshot")}</h3>
      <div className="learning-values">
        {Object.entries(event.values)
          .filter(([k]) => !["clock", "phase"].includes(k))
          .map(([key, value]) => (
            <div key={key}>
              <span>{t("field." + key)}</span>
              <strong>
                {value === null
                  ? t("value.unknown")
                  : typeof value === "boolean"
                    ? t("value." + value)
                    : value}
              </strong>
            </div>
          ))}
      </div>
      {fields.map((key) => {
        const points = events.flatMap((e, i) => {
          const v = e.values[key];
          return typeof v === "string" && Number.isFinite(Number(v))
            ? [{ i, value: Number(v), text: v, eventId: e.event_id }]
            : [];
        });
        const low = Math.min(...points.map((p) => p.value));
        const high = Math.max(...points.map((p) => p.value));
        return (
          <figure key={key}>
            <figcaption>
              {t("field." + key)} · {t("learning.recordedPoints")}
            </figcaption>
            <svg
              role="img"
              aria-label={t("field." + key)}
              viewBox="0 0 600 160"
              style={{ width: "100%", maxHeight: 160 }}
            >
              <path d="M30 15V135H575" fill="none" stroke="currentColor" />
              {points.map((p) => (
                <circle
                  key={p.eventId}
                  cx={30 + (p.i * 540) / Math.max(1, events.length - 1)}
                  cy={
                    high === low
                      ? 75
                      : 135 - ((p.value - low) * 110) / (high - low)
                  }
                  r={p.eventId === event.event_id ? 7 : 4}
                  fill="currentColor"
                  opacity={p.eventId === event.event_id ? 1 : 0.45}
                >
                  <title>{p.text}</title>
                </circle>
              ))}
            </svg>
          </figure>
        );
      })}
    </section>
  );
}
