import type { LearningTrace } from "../../lib/trace-schema";
export default function FeasibleGrid({
  trace,
  t,
}: {
  trace: LearningTrace;
  t: (k: string) => string;
}) {
  const grid = trace.tables.find((x) => x.id === "grid");
  if (!grid) return null;
  const rows = grid.rows as {
    shares: string;
    cash: string | null;
    feasible: boolean;
  }[];
  return (
    <section>
      <h3>{t("visual.lots")}</h3>
      <div className="learning-grid">
        {rows.map((r) => (
          <div key={r.shares} data-feasible={r.feasible}>
            <strong>{r.shares}</strong>
            <span>
              {t("field.feasible")}: {t("value." + r.feasible)}
            </span>
            <span>
              {t("field.cash")}: {r.cash ?? t("value.unknown")}
            </span>
          </div>
        ))}
      </div>
      <p>{t("learning.noTrajectory")}</p>
    </section>
  );
}
