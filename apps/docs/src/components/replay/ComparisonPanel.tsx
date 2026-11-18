import type { LearningTrace, Event } from "../../lib/trace-schema";
export default function ComparisonPanel({
  rows,
  t,
}: {
  rows: { trace: LearningTrace; event: Event | null }[];
  t: (k: string) => string;
}) {
  return (
    <section data-view="comparison">
      <h3>{t("learning.comparison")}</h3>
      {rows.map(({ trace, event }) => (
        <div
          key={trace.preset_id}
          data-preset={trace.preset_id}
          data-event={event?.event_id ?? "missing"}
        >
          <h4>{t("scenario." + trace.preset_id)}</h4>
          {event ? (
            <dl>
              {Object.entries(event.values).map(([k, v]) => (
                <div key={k}>
                  <dt>{t("field." + k)}</dt>
                  <dd>
                    {v === null
                      ? t("value.unknown")
                      : typeof v === "boolean"
                        ? t("value." + v)
                        : v}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p>{t("learning.noComparison")}</p>
          )}
        </div>
      ))}
    </section>
  );
}
