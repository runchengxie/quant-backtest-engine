import type { Event, LearningTrace } from "../../lib/trace-schema";
import { diagramText } from "../../lib/diagram-catalog";
import {
  alignedPathRecord,
  recordClock,
  recordMoneyUnit,
} from "../../lib/diagram-records";
import { RecordNumber, RecordValues } from "./RecordPrimitives";

type Props = {
  trace: LearningTrace;
  traces: LearningTrace[];
  event: Event;
  locale: string;
  ready: boolean;
  label: (key: string) => string;
  selectPath: (presetId: string, eventId: string) => void;
};
export default function PathsDiagram({
  trace,
  traces,
  event,
  locale,
  ready,
  label,
  selectPath,
}: Props) {
  const t = (key: Parameters<typeof diagramText>[1]) =>
    diagramText(locale, key);
  const point = trace.comparison?.points.find((p) => p.id === event.event_id);
  const first = trace.events[0];
  const common = traces.every(
    (path) =>
      path.currency === trace.currency &&
      path.units.money === trace.units.money &&
      ["cash", "quantity", "next_target"].every(
        (k) => path.events[0].values[k] === first.values[k],
      ) &&
      path.events[0].clock.value === first.clock.value,
  );
  return (
    <div className="path-diagram">
      {common && (
        <div className="path-origin">
          <span className="path-origin-dot" aria-hidden="true" />
          <span>{t("paths.origin")}</span>
          <span>
            {t("paths.cash")}{" "}
            <RecordNumber value={first.values.cash} locale={locale} />{" "}
            {recordMoneyUnit(trace, locale)}
          </span>
          <span>
            {t("paths.quantity")}{" "}
            <RecordNumber value={first.values.quantity} locale={locale} />
          </span>
        </div>
      )}
      <p className="motion-note">{t("paths.note")}</p>
      <div className="path-axis" aria-hidden="true">
        <span>{t("paths.conditions")}</span>
        <div>
          {trace.events.map((e) => (
            <span key={e.event_id}>
              {recordClock(e, locale, true)}
              <small>{label("phase." + e.stage)}</small>
            </span>
          ))}
        </div>
        <span>{t("paths.clock")}</span>
      </div>
      <div className="teaching-paths motion-paths" data-common-start={common}>
        {traces.map((path) => {
          const active = path.preset_id === trace.preset_id;
          const record = alignedPathRecord(trace, event, path);
          const reached = record
            ? path.events.findIndex((e) => e.event_id === record.event_id)
            : -1;
          return (
            <article
              className="path-lane"
              key={path.preset_id}
              data-preset={path.preset_id}
              data-active={active}
              data-aligned-record={record?.event_id ?? ""}
            >
              <h4>{label("scenario." + path.preset_id)}</h4>
              <ol className="path-events">
                {path.events.map((e, i) => {
                  const aligned =
                    point?.events[path.preset_id] === e.event_id &&
                    record !== null;
                  return (
                    <li
                      key={e.event_id}
                      data-event={e.event_id}
                      data-active={active && e.event_id === event.event_id}
                      data-reached={i <= reached}
                      data-aligned={aligned}
                    >
                      <button
                        type="button"
                        disabled={!ready}
                        aria-pressed={active && e.event_id === event.event_id}
                        onClick={() => selectPath(path.preset_id, e.event_id)}
                        aria-label={
                          diagramText(locale, "paths.inspect", {
                            name: label("scenario." + path.preset_id),
                          }) +
                          " · " +
                          recordClock(e, locale) +
                          " · " +
                          label("phase." + e.stage)
                        }
                      >
                        <span className="motion-path-point" aria-hidden="true">
                          {i + 1}
                        </span>
                        <span className="path-event-label">
                          {recordClock(e, locale, true)}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
              <RecordValues
                keys={["quantity", "cash", "next_target"]}
                event={record}
                locale={locale}
                className="path-summary"
              />
              {!record && <p className="path-no-match">{t("paths.noMatch")}</p>}
            </article>
          );
        })}
      </div>
    </div>
  );
}
