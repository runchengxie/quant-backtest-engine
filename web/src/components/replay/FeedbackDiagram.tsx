import type { Event, LearningTrace } from "../../lib/trace-schema";
import { alignedPathRecord, recordClock } from "../../lib/diagram-records";
import { RecordNumber } from "./RecordPrimitives";
import { eventText } from "../StepPlayer";
export default function FeedbackDiagram({
  trace,
  traces,
  event,
  locale,
}: {
  trace: LearningTrace;
  traces: LearningTrace[];
  event: Event;
  locale: string;
}) {
  const t = eventText(locale),
    other = traces.find((x) => x.preset_id !== trace.preset_id),
    fixed = other ? alignedPathRecord(trace, event, other) : null;
  return (
    <div
      className="motion-stage feedback-diagram"
      data-motion-stage="feedback"
      data-feedback-record={event.event_id}
    >
      <p className="diagram-meta">
        <time>{recordClock(event, locale)}</time>
      </p>
      <p className="feedback-step">
        {t("feedback.detail." + Math.min(event.ordinal, 2))}
      </p>
      <div className="feedback-route">
        <section className="feedback-account">
          <h4>{t("feedback.actual")}</h4>
          <dl>
            {[
              ["quantity", "feedback.holdings"],
              ["cash", "feedback.cash"],
            ].map(([field, label]) => (
              <div key={field}>
                <dt>{t(label)}</dt>
                <dd>
                  <RecordNumber value={event.values[field]} locale={locale} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
        <span className="feedback-arrow" aria-hidden="true">
          →
        </span>
        <section className="feedback-target" key={event.event_id}>
          <h4>{t("feedback.target")}</h4>
          <strong data-target={event.values.next_target ?? ""}>
            <RecordNumber
              value={event.values.next_target}
              locale={locale}
              percent
            />
          </strong>
        </section>
      </div>
      <p className="event-note">{t("feedback.note")}</p>
      {fixed && (
        <section className="feedback-fixed">
          <h4>
            {t(
              trace.preset_id === "feedback"
                ? "feedback.compare"
                : "feedback.adaptive",
            )}
          </h4>
          <span>
            {t("feedback.holdings")}{" "}
            <RecordNumber value={fixed.values.quantity} locale={locale} />
          </span>
          <span>
            {t("feedback.cash")}{" "}
            <RecordNumber value={fixed.values.cash} locale={locale} />
          </span>
        </section>
      )}
    </div>
  );
}
