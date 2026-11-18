import type { Event, LearningTrace } from "../../lib/trace-schema";
import { geometryValue } from "../../lib/teaching-catalog";
import {
  motionText,
  motionCaptionKey,
  type MotionKey,
} from "../../lib/motion-catalog";
import { diagramText, type DiagramKey } from "../../lib/diagram-catalog";
import { recordClock, recordMoneyUnit } from "../../lib/diagram-records";
import {
  RecordNumber,
  RecordValues,
  RecordBars,
  formatRecord,
} from "./RecordPrimitives";
import PathsDiagram from "./PathsDiagram";
import "./motion-stage.css";

type Props = {
  trace: LearningTrace;
  traces: LearningTrace[];
  event: Event;
  locale: string;
  ready: boolean;
  select: (id: string) => void;
  selectPath: (presetId: string, eventId: string) => void;
  label: (key: string) => string;
};
export default function SceneIllustration(props: Props) {
  const { trace, event, locale, ready, select, label } = props;
  const t = (key: MotionKey) => motionText(locale, key);
  const d = (key: DiagramKey) => diagramText(locale, key);
  const n = (value: Parameters<typeof formatRecord>[0]) => (
    <RecordNumber value={value} locale={locale} />
  );
  const index = trace.events.findIndex((e) => e.event_id === event.event_id);
  const previous = trace.events[index - 1];
  const fields = (keys: MotionKey[], changes = false) => (
    <RecordValues
      keys={keys}
      event={event}
      previous={changes ? previous : undefined}
      locale={locale}
    />
  );
  const bars = (keys: MotionKey[], maximum?: number) => (
    <RecordBars
      keys={keys}
      event={event}
      events={trace.events}
      maximum={maximum}
      locale={locale}
    />
  );
  const captionKey = (
    trace.scene_id === "risk" && !("predicted_variance" in event.values)
      ? "caption.account"
      : motionCaptionKey(trace.scene_id, event.stage)
  ) as MotionKey;
  const replacements: Record<string, string> = {
    stage: label("phase." + event.stage),
  };
  for (const key of Object.keys(event.values))
    replacements[key] = formatRecord(event.values[key], locale);
  for (const key of [
    "quantity",
    "cash",
    "remaining",
    "reported",
    "gross",
    "fees",
    "impact_cost",
    "transient",
    "permanent",
    "shares",
    "next_target",
    "trial",
    "score",
    "selected",
    "predicted_variance",
    "realized_squared_residual",
  ])
    replacements[key] ??= d("unknown");
  const moneyUnit = recordMoneyUnit(trace, locale);
  replacements.scenario = label("scenario." + trace.preset_id);
  if (trace.scene_id === "selection")
    replacements.score = formatRecord(
      event.values.score,
      locale,
      trace.units.score === "return fraction",
    );
  const rail = (className: string) => (
    <ol className={"record-rail " + className}>
      {trace.events.map((e, i) => (
        <li
          key={e.event_id}
          data-event={e.event_id}
          data-active={e.event_id === event.event_id}
          data-reached={i <= index}
        >
          <button
            type="button"
            disabled={!ready}
            aria-pressed={e.event_id === event.event_id}
            onClick={() => select(e.event_id)}
          >
            <span className="rail-node" aria-hidden="true">
              {i + 1}
            </span>
            <span>{label("phase." + e.stage)}</span>
            <small title={e.clock.value}>{recordClock(e, locale, true)}</small>
            {"price" in e.values && (
              <small>
                {t("price")} {n(e.values.price)}
              </small>
            )}
          </button>
        </li>
      ))}
    </ol>
  );
  return (
    <div
      className="motion-stage"
      data-motion-stage={trace.scene_id}
      data-teaching-scene={trace.scene_id}
      data-event={event.event_id}
    >
      <div className="diagram-meta">
        <span>{d("record")}</span>
        <time title={event.clock.value}>{recordClock(event, locale)}</time>
      </div>
      <p className="motion-caption">
        {motionText(locale, captionKey, replacements)}
      </p>

      {trace.scene_id === "flow" && (
        <>
          <div
            className="teaching-transfer motion-transfer"
            data-transfer={index > 0}
          >
            {trace.events.map((record, i) => (
              <div
                key={record.event_id}
                data-active={record.event_id === event.event_id}
                data-reached={i <= index}
              >
                <button
                  type="button"
                  disabled={!ready}
                  aria-pressed={record.event_id === event.event_id}
                  onClick={() => select(record.event_id)}
                >
                  <span className="transfer-node" aria-hidden="true">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>{label("phase." + record.stage)}</span>
                  <small title={record.clock.value}>
                    {recordClock(record, locale, true)}
                  </small>
                </button>
                <dl className="flow-account">
                  <div>
                    <dt>{t("cash")}</dt>
                    <dd>{n(record.values.cash)}</dd>
                  </div>
                  <div>
                    <dt>{t("quantity")}</dt>
                    <dd>{n(record.values.quantity)}</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
          {fields(["fees", "price"], true)}
          <p className="motion-note diagram-unit">
            {moneyUnit} · {d("unit.shares")}
          </p>
        </>
      )}

      {trace.scene_id === "book" && (
        <>
          <div className="book-key">
            <span>
              <i className="key-filled" />
              {d("book.legend")}
            </span>
            <span>
              <i className="key-empty" />
              {d("book.unfilled")}
            </span>
            <span>
              <i className="key-reported" />
              {d("book.reported")}
            </span>
          </div>
          <div className="motion-shares" aria-label={t("blocks")}>
            {Array.from(
              {
                length: Math.max(
                  0,
                  Math.min(
                    100,
                    geometryValue(trace.events[0]?.values.remaining) ?? 0,
                  ),
                ),
              },
              (_, i) => (
                <span
                  key={i}
                  data-filled={i < (geometryValue(event.values.quantity) ?? 0)}
                  data-reported={
                    i < (geometryValue(event.values.reported) ?? 0)
                  }
                />
              ),
            )}
          </div>
          <p className="motion-note">{d("book.note")}</p>
          {fields(["quantity", "remaining", "reported"], true)}
          {rail("teaching-ladder motion-steps")}
        </>
      )}

      {trace.scene_id === "cost" && (
        <>
          <div className="cost-plot teaching-bars">
            <div className="cost-axis">
              <span>0</span>
              <span>
                {formatRecord(
                  String(
                    Math.max(
                      1,
                      ...trace.events.map(
                        (e) => geometryValue(e.values.gross) ?? 0,
                      ),
                    ),
                  ),
                  locale,
                )}{" "}
                {moneyUnit}
              </span>
            </div>
            {(["gross", "fees"] as const).map((key) => {
              const maximum = Math.max(
                1,
                ...trace.events.map((e) => geometryValue(e.values.gross) ?? 0),
              );
              const value = geometryValue(event.values[key]);
              return (
                <div className="cost-row" key={key} data-field={key}>
                  <span>{t(key)}</span>
                  <div className="motion-track">
                    <span
                      className="motion-bar"
                      style={{
                        width: `${(Math.abs(value ?? 0) / maximum) * 100}%`,
                      }}
                    />
                  </div>
                  {n(event.values[key])}
                </div>
              );
            })}
            <div className="cost-inclusion" data-field="impact_cost">
              <span className="inclusion-bracket" aria-hidden="true" />
              <span>
                {t("impact_cost")} {n(event.values.impact_cost)}
                <small>{d("cost.included")}</small>
              </span>
            </div>
          </div>
          <p className="motion-note">{d("cost.note")}</p>
          {fields(["cash", "price", "quantity"], true)}
        </>
      )}

      {trace.scene_id === "impact" && (
        <>
          <div className="chart-legend">
            <span className="legend-transient">{t("transient")}</span>
            <span className="legend-permanent">{t("permanent")}</span>
            <span className="diagram-axis-unit">
              {moneyUnit} / {d("unit.shares")}
            </span>
          </div>
          <svg
            className="teaching-curves motion-curves"
            viewBox="0 0 680 290"
            role="img"
            aria-label={t("ordinal")}
          >
            {(() => {
              const max = Math.max(
                0.001,
                ...trace.events.flatMap((e) => [
                  geometryValue(e.values.transient) ?? 0,
                  geometryValue(e.values.permanent) ?? 0,
                ]),
              );
              const x = (i: number) =>
                90 + (i / Math.max(1, trace.events.length - 1)) * 515;
              const y = (v: number) => 218 - (v / max) * 170;
              return (
                <>
                  {[0, 0.5, 1].map((r) => (
                    <g key={r}>
                      <line
                        className="chart-gridline"
                        x1="90"
                        y1={y(max * r)}
                        x2="620"
                        y2={y(max * r)}
                      />
                      <text x="76" y={y(max * r) + 5} textAnchor="end">
                        {formatRecord(String(max * r), locale)}
                      </text>
                    </g>
                  ))}
                  <line
                    className="chart-current"
                    x1={x(index)}
                    y1="35"
                    x2={x(index)}
                    y2="226"
                  />
                  {(["transient", "permanent"] as const).map((key, line) => (
                    <g key={key} className={`teaching-curve-${line}`}>
                      <polyline
                        className="motion-curve-context"
                        points={trace.events
                          .flatMap((e, i) => {
                            const v = geometryValue(e.values[key]);
                            return v === null ? [] : [`${x(i)},${y(v)}`];
                          })
                          .join(" ")}
                      />
                      {trace.events.slice(1).map((e, i) => {
                        const a = geometryValue(trace.events[i].values[key]),
                          b = geometryValue(e.values[key]);
                        return a === null || b === null ? null : (
                          <polyline
                            key={e.event_id}
                            className="motion-curve-segment"
                            data-revealed={i < index}
                            points={`${x(i)},${y(a)} ${x(i + 1)},${y(b)}`}
                          />
                        );
                      })}
                      {trace.events.map((e, i) => {
                        const v = geometryValue(e.values[key]);
                        return v === null ? null : (
                          <circle
                            key={e.event_id}
                            cx={x(i)}
                            cy={y(v)}
                            r={i === index ? 6 : 3}
                            data-active={i === index}
                          >
                            <title>{`${t(key)} ${String(e.values[key])}`}</title>
                          </circle>
                        );
                      })}
                    </g>
                  ))}
                  {trace.events.map((e, i) => (
                    <g key={e.event_id}>
                      <text x={x(i)} y="250" textAnchor="middle">
                        {i + 1}
                      </text>
                      <text
                        className="clock-label"
                        x={x(i)}
                        y="275"
                        textAnchor="middle"
                      >
                        {recordClock(e, locale, true)}
                      </text>
                    </g>
                  ))}
                </>
              );
            })()}
          </svg>
          <p className="motion-note">{d("impact.note")}</p>
          {fields(["transient", "permanent", "offset", "price", "unaffected"])}
        </>
      )}

      {trace.scene_id === "lots" && (
        <>
          <div className="lattice-heading">
            <span>{d("lots.a")} ↓</span>
            <span>{d("lots.b")} →</span>
          </div>
          <div className="lattice-column-labels" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <span key={i}>{i}</span>
            ))}
          </div>
          <div className="lattice-with-axis">
            <div className="lattice-row-labels" aria-hidden="true">
              {[0, 1, 2, 3].map((i) => (
                <span key={i}>{i}</span>
              ))}
            </div>
            <div className="teaching-landscape motion-grid" role="list">
              {(
                (trace.tables.find((t) => t.id === "grid")?.rows ?? []) as {
                  shares: string;
                  cash: string | null;
                  feasible: boolean;
                }[]
              ).map((row) => {
                const selected = row.shares === event.values.shares;
                const title =
                  motionText(locale, "grid.pair", {
                    a: row.shares.split(",")[0],
                    b: row.shares.split(",")[1] ?? d("unknown"),
                  }) +
                  " · " +
                  t(row.feasible ? "feasible" : "infeasible") +
                  " · " +
                  t("cash") +
                  " " +
                  formatRecord(row.cash, locale) +
                  (selected ? " · " + d("selected") : "");
                return (
                  <div
                    role="listitem"
                    tabIndex={0}
                    key={row.shares}
                    data-value={row.shares}
                    data-feasible={row.feasible}
                    data-selected={selected}
                    title={title}
                    aria-label={title}
                  >
                    <span className="candidate-mark" aria-hidden="true">
                      {row.feasible ? "○" : "×"}
                    </span>
                    <small>
                      {row.feasible
                        ? formatRecord(row.cash, locale)
                        : d("infeasible")}
                    </small>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="chart-legend">
            <span>○ {d("feasible")}</span>
            <span>× {d("infeasible")}</span>
            <span className="legend-selected">{d("selected")}</span>
          </div>
          <p className="motion-note">
            {d("lots.note")} {t("cash")} · {moneyUnit}
          </p>
          {fields(["shares", "cash", "fees", "error"], true)}
        </>
      )}

      {trace.scene_id === "paths" && <PathsDiagram {...props} />}

      {trace.scene_id === "selection" && (
        <>
          <div className="selection-axis" aria-hidden="true">
            <span />
            <div>
              {(() => {
                const max = Math.max(
                  0.001,
                  ...trace.events.map((e) =>
                    Math.abs(geometryValue(e.values.score) ?? 0),
                  ),
                );
                return (
                  <>
                    <span>
                      {formatRecord(
                        String(-max),
                        locale,
                        trace.units.score === "return fraction",
                      )}
                    </span>
                    <span>0</span>
                    <span>
                      {formatRecord(
                        String(max),
                        locale,
                        trace.units.score === "return fraction",
                      )}
                    </span>
                  </>
                );
              })()}
            </div>
            <span />
          </div>
          <div className="teaching-trials motion-trials">
            {trace.events.map((e) => {
              const value = geometryValue(e.values.score),
                max = Math.max(
                  0.001,
                  ...trace.events.map((x) =>
                    Math.abs(geometryValue(x.values.score) ?? 0),
                  ),
                );
              const length = (Math.abs(value ?? 0) / max) * 45;
              return (
                <button
                  key={e.event_id}
                  type="button"
                  disabled={!ready}
                  data-event={e.event_id}
                  aria-pressed={e.event_id === event.event_id}
                  onClick={() => select(e.event_id)}
                >
                  <span className="trial-name">
                    {t("trial")} {formatRecord(e.values.trial, locale)}
                    <small title={String(e.values.shares)}>
                      {String(e.values.shares ?? d("unknown"))
                        .split(",")
                        .map((name) =>
                          /^SYN_[A-Z]$/.test(name) ? name.slice(4) : name,
                        )
                        .join(" / ")}
                    </small>
                  </span>
                  <span className="signed-score">
                    <span className="score-zero" />
                    <span
                      className="score-fill"
                      data-sign={(value ?? 0) < 0 ? "negative" : "positive"}
                      style={{
                        left: `${value !== null && value < 0 ? 50 - length : 50}%`,
                        width: `${length}%`,
                      }}
                    />
                  </span>
                  <span className="trial-value">
                    {
                      <RecordNumber
                        value={e.values.score}
                        locale={locale}
                        percent={trace.units.score === "return fraction"}
                      />
                    }
                    {e.values.selected === true && (
                      <small className="selection-mark">{d("selected")}</small>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
          <p className="motion-note">{d("selection.note")}</p>
        </>
      )}

      {trace.scene_id === "risk" && (
        <>
          {"predicted_variance" in event.values ? (
            <>
              <div className="risk-pair teaching-bars">
                <div className="risk-unit">{d("unit.variance")}</div>
                {(
                  ["predicted_variance", "realized_squared_residual"] as const
                ).map((key) => {
                  const maximum = Math.max(
                    0.001,
                    ...trace.events.flatMap((e) => [
                      geometryValue(e.values.predicted_variance) ?? 0,
                      geometryValue(e.values.realized_squared_residual) ?? 0,
                    ]),
                  );
                  const value = geometryValue(event.values[key]);
                  return (
                    <div key={key} data-field={key}>
                      <span>{t(key)}</span>
                      <span className="risk-scale">
                        <i />
                        {value !== null && (
                          <b
                            className="risk-point"
                            style={{ left: `${(value / maximum) * 90 + 5}%` }}
                          />
                        )}
                      </span>
                      {n(event.values[key])}
                    </div>
                  );
                })}
                <div className="risk-axis">
                  <span />
                  <div>
                    <span>0</span>
                    <span>
                      {formatRecord(
                        String(
                          Math.max(
                            0.001,
                            ...trace.events.flatMap((e) => [
                              geometryValue(e.values.predicted_variance) ?? 0,
                              geometryValue(
                                e.values.realized_squared_residual,
                              ) ?? 0,
                            ]),
                          ),
                        ),
                        locale,
                      )}
                    </span>
                  </div>
                  <span />
                </div>
              </div>
              <p className="motion-note">{d("risk.note")}</p>
              {fields(
                (["coverage", "variance_ratio"] as MotionKey[]).filter(
                  (k) => k in event.values,
                ),
              )}
            </>
          ) : (
            <>
              {bars([
                "cash",
                ...("wealth" in event.values ? ["wealth" as const] : []),
              ])}
              {fields(
                (
                  [
                    "quantity",
                    "cash_realized_wealth",
                    "report_pending",
                    "cash_right",
                    "stock_right",
                    "capital_flow",
                    "gross",
                    "fees",
                    "impact_cost",
                  ] as MotionKey[]
                ).filter((k) => k in event.values),
                true,
              )}
            </>
          )}
        </>
      )}
      <p className="motion-note motion-precision">{t("precision")}</p>
    </div>
  );
}
