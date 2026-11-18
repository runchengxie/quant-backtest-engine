import type { Event, LearningTrace, Scalar } from "../../lib/trace-schema";
import { teachingText, type TeachingKey } from "../../lib/teaching-catalog";
import FeedbackDiagram from "./FeedbackDiagram";
import { eventText } from "../StepPlayer";
import SceneIllustration from "./SceneIllustration";
import OpportunityExample from "./OpportunityExample";
import "./teaching.css";
type Props = {
  presentation?: "feedback";
  trace: LearningTrace;
  traces: LearningTrace[];
  event: Event;
  locale: string;
  ready: boolean;
  select: (id: string) => void;
  selectPath: (presetId: string, eventId: string) => void;
  label: (key: string) => string;
};
export default function TeachingScenes(props: Props) {
  const { trace, event, locale } = props;
  const t = (key: TeachingKey) => teachingText(locale, key);
  const value = (v: Scalar | undefined) =>
    v == null
      ? t("unknown")
      : typeof v === "boolean"
        ? t(v ? "true" : "false")
        : v;
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
  return (
    <div
      className="teaching-scenes"
      data-teaching-scene={trace.scene_id}
      data-event={event.event_id}
    >
      <section className="teaching-main">
        <h3>
          {props.presentation === "feedback"
            ? eventText(locale)("feedback.title")
            : t(
                (trace.scene_id === "flow"
                  ? "flow.visual"
                  : trace.scene_id + ".title") as TeachingKey,
              )}
        </h3>
        {props.presentation === "feedback" ? (
          <FeedbackDiagram {...props} />
        ) : (
          <SceneIllustration {...props} />
        )}
      </section>
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
