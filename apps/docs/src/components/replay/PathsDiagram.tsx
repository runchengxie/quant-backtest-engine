import type { Event, LearningTrace } from "../../lib/trace-schema";
import { diagramText } from "../../lib/diagram-catalog";
import {
  alignedPathRecord,
  recordClock,
  recordMoneyUnit,
} from "../../lib/diagram-records";
import { recordedPathGeometry } from "../../lib/path-geometry";
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
  const geometry = recordedPathGeometry(trace, traces);
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
    <div className="path-diagram" data-trajectory={geometry !== null}>
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
      {geometry && <p className="path-scale">{diagramText(locale, "paths.scale", {maximum: new Intl.NumberFormat(locale).format(geometry.maximum)})}</p>}
      <div className="path-axis" aria-hidden="true">
        <span>{t("paths.conditions")}</span>
        <div>
          {trace.events.map((e, i) => (
            <span key={e.event_id} style={geometry ? {left: `${geometry.x[i]}%`} : undefined}>
              {recordClock(e, locale, true)}
              <small>{label("phase." + e.stage)}</small>
            </span>
          ))}
        </div>
        <span>{t("paths.clock")}</span>
      </div>
      <div className="teaching-paths motion-paths" data-common-start={common}>
        {traces.map((path) => {
          const coordinates = geometry?.paths.get(path.preset_id);
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
              <div className="path-plot" data-trajectory={!!coordinates}>
                {coordinates && <svg className="path-trajectory" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
                  <line x1="12" x2="88" y1="80" y2="80" className="path-zero" vectorEffect="non-scaling-stroke" />
                  <polyline points={coordinates.map(p => `${p.x},${p.y}`).join(" ")} className="path-record-line" vectorEffect="non-scaling-stroke" />
                  {reached > 0 && <polyline points={coordinates.slice(0,reached+1).map(p => `${p.x},${p.y}`).join(" ")} className="path-observed-line" vectorEffect="non-scaling-stroke" />}
                </svg>}
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
                        style={coordinates ? {left:`${coordinates[i].x}%`,top:`${coordinates[i].y}%`} : undefined}
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
                          label("phase." + e.stage) +
                          (coordinates ? " · " + t("paths.quantity") + " " + String(e.values.quantity) : "")
                        }
                      >
                        <span className="motion-path-point" aria-hidden="true">
                          {i + 1}
                        </span>
                        {coordinates && <span className="path-record-quantity"><RecordNumber value={e.values.quantity} locale={locale}/></span>}
                        <span className="path-event-label">
                          {recordClock(e, locale, true)}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
              </div>
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
