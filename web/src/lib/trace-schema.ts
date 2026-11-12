import Ajv2020 from "ajv/dist/2020.js";
import schema from "../../../docs/assets/learning/schemas/trace.schema.json" with { type: "json" };
export type Scalar = string | boolean | null;
export type ValueSource = {
  source_pointer: string;
  run_names: string[];
  run_binding_status: string;
  reason_key: string | null;
};
export type Event = {
  event_id: string;
  ordinal: number;
  clock: { kind: string; value: string; timezone: string | null };
  stage: string;
  depends_on: string[];
  values: Record<string, Scalar>;
  source_pointers: Record<string, ValueSource>;
};
export type LearningTrace = {
  schema: string;
  scene_id: string;
  preset_id: string;
  provider: { id: string; revision: string; url: string };
  bindings: {
    run_sha256: Record<string, string>;
    calls: Record<string, unknown>;
    [key: string]: unknown;
  };
  units: Record<string, string>;
  currency: string;
  calibration: string;
  evidence_boundary: string;
  events: Event[];
  tables: {
    id: string;
    rows: unknown;
    source_pointer: string;
    value_sources: Record<string, ValueSource>;
  }[];
  comparison?: {
    axis: string;
    points: {
      id: string;
      label_key: string;
      events: Record<string, string | null>;
    }[];
  };
};
const validator = new Ajv2020({ strict: false, allErrors: true }).compile(
  schema,
);
export function isLearningTrace(value: unknown): value is LearningTrace {
  if (!validator(value)) return false;
  const t = value as LearningTrace;
  if (
    Object.keys(t.bindings.calls).sort().join() !==
    Object.keys(t.bindings.run_sha256).sort().join()
  )
    return false;
  const ids = new Set<string>();
  return t.events.every((e, i) => {
    const good =
      e.ordinal === i &&
      !ids.has(e.event_id) &&
      e.depends_on.every((id) => ids.has(id)) &&
      Object.keys(e.values).sort().join() ===
        Object.keys(e.source_pointers).sort().join();
    ids.add(e.event_id);
    return good;
  });
}
