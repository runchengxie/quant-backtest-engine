import type { Event } from "../../lib/trace-schema";
export default function EventTimeline({
  events,
  ordinal,
  ready,
  t,
  select,
  step,
}: {
  events: Event[];
  ordinal: number;
  ready: boolean;
  t: (k: string) => string;
  select: (id: string) => void;
  step: (type: "NEXT" | "PREVIOUS") => void;
}) {
  return (
    <section
      tabIndex={0}
      aria-label={t("learning.timeline")}
      onKeyDown={(e) => {
        if (e.target !== e.currentTarget) return;
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          step(e.key === "ArrowRight" ? "NEXT" : "PREVIOUS");
        }
      }}
    >
      <ol className="learning-timeline">
        {events.map((e) => (
          <li key={e.event_id}>
            <button
              disabled={!ready}
              aria-current={e.ordinal === ordinal ? "step" : undefined}
              onClick={() => select(e.event_id)}
            >
              {t("phase." + e.stage)} <code>{e.clock.value}</code>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
