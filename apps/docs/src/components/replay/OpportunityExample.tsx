import { useState } from "react";
import fixture from "../../../../../docs/assets/learning/opportunity.json";
import {
  geometryValue,
  signedGeometry,
  teachingText,
  type TeachingKey,
} from "../../lib/teaching-catalog";
type ExampleCase = {
  id: string;
  inputs: { parents: { opportunity_price?: string | null }[] };
  outputs: {
    parents: {
      opportunity_shortfall?: string | null;
      reference_shortfall_with_recorded_fees?: string | null;
    }[];
  };
};
export default function OpportunityExample({ locale }: { locale: string }) {
  const data = fixture as unknown as {
    cases: ExampleCase[];
    receipt: { payload_sha256: string };
    provenance: {
      api: string;
      provider_revision: string;
      wheel: { sha256: string };
      source: { sha256: string };
    };
  };
  const [caseId, setCaseId] = useState(data.cases[0]?.id);
  const example = data.cases.find((c) => c.id === caseId);
  const t = (key: TeachingKey) => teachingText(locale, key);
  if (!example) return <p>{t("unknown")}</p>;
  const output = example.outputs.parents[0];
  const maximum = Math.max(
    0.001,
    ...data.cases.flatMap((c) =>
      [
        c.outputs.parents[0]?.opportunity_shortfall,
        c.outputs.parents[0]?.reference_shortfall_with_recorded_fees,
      ].map((v) => Math.abs(geometryValue(v) ?? 0)),
    ),
  );
  const rows: { key: TeachingKey; value: string | null | undefined }[] = [
    {
      key: "opportunity.executed",
      value: output?.reference_shortfall_with_recorded_fees,
    },
    { key: "opportunity.unfilled", value: output?.opportunity_shortfall },
  ];
  return (
    <div className="teaching-opportunity-example" data-example-id={example.id}>
      <p>{t("opportunity.note")}</p>
      <label>
        {t("opportunity.end")}{" "}
        <select value={caseId} onChange={(e) => setCaseId(e.target.value)}>
          {data.cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.inputs.parents[0]?.opportunity_price ?? t("unknown")}
            </option>
          ))}
        </select>
      </label>
      <div className="teaching-signed-rows">
        {rows.map((row) => {
          const geometry = signedGeometry(row.value, maximum);
          const positive = (geometryValue(row.value) ?? 0) > 0;
          return (
            <div key={row.key} data-example-field={row.key}>
              <span>{t(row.key)}</span>
              <div className="teaching-signed-track">
                <span className="teaching-zero" />
                {geometry && (
                  <span
                    className="teaching-signed-bar"
                    data-positive={positive}
                    style={{
                      left: `${geometry.x}%`,
                      width: `${geometry.width}%`,
                    }}
                  />
                )}
              </div>
              <strong>
                {row.value == null
                  ? t("unknown")
                  : (positive ? "+" : "") + row.value}
              </strong>
            </div>
          );
        })}
      </div>
      <p>{t("opportunity.interpret")}</p>
      <details>
        <summary>{t("opportunity.provenance")}</summary>
        <table>
          <thead>
            <tr>
              <th>{t("opportunity.end")}</th>
              <th>{t("opportunity.executed")}</th>
              <th>{t("opportunity.unfilled")}</th>
            </tr>
          </thead>
          <tbody>
            {data.cases.map((c) => (
              <tr key={c.id}>
                <td>
                  {c.inputs.parents[0]?.opportunity_price ?? t("unknown")}
                </td>
                <td>
                  {c.outputs.parents[0]
                    ?.reference_shortfall_with_recorded_fees ?? t("unknown")}
                </td>
                <td>
                  {c.outputs.parents[0]?.opportunity_shortfall ?? t("unknown")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>{t("opportunity.limit")}</p>
        <dl>
          {(
            [
              ["opportunity.hash", data.receipt.payload_sha256],
              ["opportunity.api", data.provenance.api],
              ["opportunity.revision", data.provenance.provider_revision],
              ["opportunity.wheel", data.provenance.wheel.sha256],
              ["opportunity.source", data.provenance.source.sha256],
            ] as [TeachingKey, string][]
          ).map(([key, value]) => (
            <div key={key}>
              <dt>{t(key)}</dt>
              <dd>
                <code>{value}</code>
              </dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
