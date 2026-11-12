import type { Event } from "../../lib/trace-schema";
export default function CausalFlow({
  event,
  t,
}: {
  event: Event;
  t: (k: string) => string;
}) {
  return (
    <section data-view="causal" data-event={event.event_id}>
      <h3>{t("learning.recordedStage")}</h3>
      <p>
        {t("phase." + event.stage)} · <code>{event.clock.kind}</code> ·{" "}
        <code>{event.clock.value}</code>
      </p>
      <p>{t("learning.noInventedStages")}</p>
    </section>
  );
}
