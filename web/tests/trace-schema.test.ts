import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { isLearningTrace } from "../src/lib/trace-schema.ts";
test("schema rejects unsafe clocks and missing call map", () => {
  const t = JSON.parse(
    readFileSync(
      new URL(
        "../../docs/assets/learning/traces/flow/roundtrip.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.ok(isLearningTrace(t));
  (t.events[0].clock as unknown as { value: unknown }).value =
    Number.MAX_SAFE_INTEGER + 1;
  assert.equal(isLearningTrace(t), false);
});
