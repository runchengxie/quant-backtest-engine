import type { Event, LearningTrace, Scalar } from "../../lib/trace-schema";
import {
  geometryValue,
  relativeWidth,
  teachingText,
  type TeachingKey,
} from "../../lib/teaching-catalog";
import "./teaching.css";
import OpportunityExample from "./OpportunityExample";
export default function TeachingScenes({
  trace,
  traces,
  event,
  locale,
  ready,
  select,
  label,
}: {
  trace: LearningTrace;
  traces: LearningTrace[];
  event: Event;
  locale: string;
  ready: boolean;
  select: (id: string) => void;
  label: (key: string) => string;
}) {
  const t = (key: TeachingKey) => teachingText(locale, key);
  const value = (v: Scalar | undefined) =>
    v == null
      ? t("unknown")
      : typeof v === "boolean"
        ? t(String(v) as "true" | "false")
        : v;
  const fields = (keys: TeachingKey[]) => (
    <dl className="teaching-values">
      {keys.map((key) => (
        <div key={key}>
          <dt>{t(key)}</dt>
          <dd>{value(event.values[key])}</dd>
        </div>
      ))}
    </dl>
  );
  const bars = (keys: TeachingKey[]) => {
    const maximum = Math.max(
      0,
      ...trace.events.flatMap((e) =>
        keys.map((k) => geometryValue(e.values[k]) ?? 0),
      ),
    );
    return (
      <div className="teaching-bars">
        {keys.map((key) => {
          const width = relativeWidth(event.values[key], maximum);
          return (
            <div key={key} data-field={key}>
              <span>{t(key)}</span>
              <div className="teaching-track">
                {width !== null && (
                  <span
                    className={"teaching-bar teaching-" + key}
                    style={{ width: `${width}%` }}
                  />
                )}
              </div>
              <strong>{value(event.values[key])}</strong>
            </div>
          );
        })}
      </div>
    );
  };
  const nodes: { key: TeachingKey; fields: string[] }[] = [
    { key: "flow.forecast", fields: [] },
    { key: "flow.target", fields: [] },
    { key: "flow.order", fields: ["pending", "remaining"] },
    {
      key: "flow.execution",
      fields: [
        "price",
        "reported",
        ...(trace.scene_id === "book" || trace.scene_id === "impact"
          ? ["quantity"]
          : []),
      ],
    },
    {
      key: "flow.account",
      fields: [
        "cash",
        ...(trace.scene_id === "flow" || trace.scene_id === "paths"
          ? ["quantity"]
          : []),
        "fees",
      ],
    },
    { key: "flow.replan", fields: ["next_target"] },
  ];
  const grid = trace.tables.find((table) => table.id === "grid");
  const rows =
    grid && Array.isArray(grid.rows)
      ? (grid.rows as {
          shares: string;
          cash: string | null;
          feasible: boolean;
        }[])
      : [];
  return (
    <div
      className="teaching-scenes"
      data-teaching-scene={trace.scene_id}
      data-event={event.event_id}
    >
      {trace.scene_id === "flow" && (
        <section>
          <h3>{t("flow.visual")}</h3>
          <div className="teaching-transfer">
            <span>{t("flow.order")}</span>
            <b aria-hidden="true">→</b>
            <span>{label("phase." + event.stage)}</span>
            <b aria-hidden="true">→</b>
            <span>{t("flow.account")}</span>
          </div>
          {fields(["cash", "quantity", "fees"])}
        </section>
      )}
      {trace.scene_id === "cost" && (
        <section>
          <h3>{t("cost.title")}</h3>
          {bars(["gross", "fees", "impact_cost"])}
          {fields(["cash", "price"])}
          <p>{t("cost.note")}</p>
        </section>
      )}
      {trace.scene_id === "selection" && (
        <section>
          <h3>{t("selection.title")}</h3>
          <p>{t("selection.note")}</p>
          <div className="teaching-trials">
            {trace.events.map((e) => {
              const n = geometryValue(e.values.score);
              const max = Math.max(
                ...trace.events.map((x) =>
                  Math.abs(geometryValue(x.values.score) ?? 0),
                ),
                0.001,
              );
              return (
                <button
                  key={e.event_id}
                  type="button"
                  disabled={!ready}
                  data-event={e.event_id}
                  aria-pressed={event.event_id === e.event_id}
                  onClick={() => select(e.event_id)}
                >
                  <span>
                    {t("trial")} {value(e.values.trial)}
                  </span>
                  <svg viewBox="0 0 80 160" role="img" aria-label={t("score")}>
                    <line
                      x1="0"
                      x2="80"
                      y1="80"
                      y2="80"
                      stroke="currentColor"
                    />
                    {n !== null && (
                      <rect
                        x="20"
                        width="40"
                        y={n >= 0 ? 80 - (n / max) * 65 : 80}
                        height={(Math.abs(n) / max) * 65}
                        fill="currentColor"
                      />
                    )}
                  </svg>
                  <strong>{value(e.values.score)}</strong>
                  <span>{value(e.values.shares)}</span>
                  {e.values.selected === true && <b>{t("selected")}</b>}
                </button>
              );
            })}
          </div>
        </section>
      )}
      {trace.scene_id === "risk" && (
        <section>
          <h3>{t("risk.title")}</h3>
          <p>{t("risk.note")}</p>
          {"predicted_variance" in event.values ? (
            bars(["predicted_variance", "realized_squared_residual"])
          ) : (
            <>
              {bars(["cash", "wealth"])}
              {fields(["quantity", "cash_realized_wealth"])}
            </>
          )}
        </section>
      )}
      {trace.scene_id === "book" && (
        <section>
          <h3>{t("book.title")}</h3>
          <p>{t("book.note")}</p>
          {bars(["quantity", "remaining", "reported"])}
          <ol className="teaching-ladder">
            {trace.events.map((e) => (
              <li
                key={e.event_id}
                data-event={e.event_id}
                data-active={e.event_id === event.event_id}
              >
                <button
                  type="button"
                  disabled={!ready}
                  aria-pressed={e.event_id === event.event_id}
                  onClick={() => select(e.event_id)}
                >
                  {label("phase." + e.stage)} · {t("price")}:{" "}
                  {value(e.values.price)} · {t("quantity")}:{" "}
                  {value(e.values.quantity)} · {t("reported")}:{" "}
                  {value(e.values.reported)}
                </button>
              </li>
            ))}
          </ol>
          <p>{t("book.report")}</p>
        </section>
      )}
      {trace.scene_id === "impact" && (
        <section>
          <h3>{t("impact.title")}</h3>
          <p>{t("impact.note")}</p>
          <svg
            className="teaching-curves"
            viewBox="0 0 600 200"
            role="img"
            aria-label={t("impact.title")}
          >
            <line x1="25" y1="175" x2="575" y2="175" stroke="currentColor" />
            {(["transient", "permanent"] as const).map((key, line) => {
              const max = Math.max(
                0.001,
                ...trace.events.flatMap((e) => [
                  geometryValue(e.values.transient) ?? 0,
                  geometryValue(e.values.permanent) ?? 0,
                ]),
              );
              const points = trace.events.flatMap((e, i) => {
                const n = geometryValue(e.values[key]);
                return n === null
                  ? []
                  : [
                      {
                        x:
                          25 + (i / Math.max(1, trace.events.length - 1)) * 550,
                        y: 175 - (n / max) * 140,
                        e,
                      },
                    ];
              });
              return (
                <g key={key} className={"teaching-curve-" + line}>
                  <polyline
                    points={points.map((p) => `${p.x},${p.y}`).join(" ")}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                  />
                  {points.map((p) => (
                    <circle
                      key={p.e.event_id}
                      cx={p.x}
                      cy={p.y}
                      r={p.e.event_id === event.event_id ? 7 : 4}
                    >
                      <title>{`${t(key)}: ${value(p.e.values[key])}`}</title>
                    </circle>
                  ))}
                </g>
              );
            })}
          </svg>
          {fields(["transient", "permanent"])}
          {fields(["offset", "unaffected", "price"])}
        </section>
      )}
      {rows.length > 0 && (
        <section>
          <h3>{t("lots.title")}</h3>
          <p>{t("lots.note")}</p>
          <div className="teaching-landscape" role="list">
            {rows.map((row) => (
              <div
                role="listitem"
                key={row.shares}
                data-feasible={row.feasible}
                data-selected={row.shares === event.values.shares}
              >
                <strong>{row.shares}</strong>
                <span>{t(row.feasible ? "feasible" : "infeasible")}</span>
                <span>
                  {t("cash")}: {value(row.cash)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
      {trace.scene_id === "paths" && (
        <section>
          <h3>{t("paths.title")}</h3>
          <p>{t("paths.note")}</p>
          <div className="teaching-paths">
            {traces.map((path) => (
              <article key={path.preset_id} data-preset={path.preset_id}>
                <h4>{label("scenario." + path.preset_id)}</h4>
                <ol>
                  {path.events.map((e) => (
                    <li
                      key={e.event_id}
                      data-event={e.event_id}
                      data-active={e.event_id === event.event_id}
                    >
                      <button
                        type="button"
                        disabled={!ready || path.preset_id !== trace.preset_id}
                        aria-pressed={e.event_id === event.event_id}
                        onClick={() => select(e.event_id)}
                      >
                        {label("phase." + e.stage)}
                        <span>
                          {t("cash")}: {value(e.values.cash)}
                        </span>
                        <span>
                          {t("quantity")}: {value(e.values.quantity)}
                        </span>
                        <span>
                          {t("next_target")}: {value(e.values.next_target)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>
              </article>
            ))}
          </div>
        </section>
      )}
      <details className="teaching-map">
        <summary>{t("map")}</summary>
        <h3>{t("flow.title")}</h3>
        <p>{t("flow.note")}</p>
        <ol>
          {nodes.map((node) => (
            <li
              key={node.key}
              data-known={node.fields.some((k) => event.values[k] != null)}
            >
              <strong>{t(node.key)}</strong>
              <p>{t((node.key + ".note") as TeachingKey)}</p>
              <dl>
                {node.fields.length ? (
                  node.fields.map((key) => (
                    <div key={key}>
                      <dt>{t(key as TeachingKey)}</dt>
                      <dd>{value(event.values[key])}</dd>
                    </div>
                  ))
                ) : (
                  <div>
                    <dt>{t("value")}</dt>
                    <dd>{t("unknown")}</dd>
                  </div>
                )}
              </dl>
            </li>
          ))}
        </ol>
      </details>
      {trace.scene_id === "cost" && (
        <details className="teaching-opportunity">
          <summary>{t("opportunity.title")}</summary>
          <OpportunityExample locale={locale} />
        </details>
      )}
      {(trace.scene_id === "book" || trace.scene_id === "paths") && (
        <details className="teaching-opportunity">
          <summary>{t("cost.title")}</summary>
          <p>{t("cost.note")}</p>
          <p>{t("cost.formula")}</p>
        </details>
      )}
    </div>
  );
}
