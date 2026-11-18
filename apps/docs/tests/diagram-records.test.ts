import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  alignedPathRecord,
  recordClock,
  recordMoneyUnit,
} from "../src/lib/diagram-records.ts";
import { reduceReplay, initialState } from "../src/lib/replay-state.ts";
import type { LearningTrace } from "../src/lib/trace-schema.ts";
const path = (id: string) =>
  JSON.parse(
    readFileSync(
      new URL(
        `../../../docs/assets/learning/traces/paths/${id}.json`,
        import.meta.url,
      ),
      "utf8",
    ),
  ) as LearningTrace;

test("path comparison uses explicit mapping, never row index fallback", () => {
  const a = path("thin"),
    b = path("deep");
  assert.equal(alignedPathRecord(a, a.events[1], b)?.values.quantity, "500");
  a.comparison!.points[1].events.deep = null;
  assert.equal(alignedPathRecord(a, a.events[1], b), null);
});
test("mapping with a different clock or stage is unavailable", () => {
  const a = path("thin"),
    b = path("deep");
  b.events[1].clock.value = "1767576780000000001";
  assert.equal(alignedPathRecord(a, a.events[1], b), null);
});
test("atomic path selection pauses and preserves the requested record", () => {
  const a = path("thin"),
    b = path("deep"),
    index = new Map([
      [a.preset_id, a],
      [b.preset_id, b],
    ]);
  const state = { ...initialState("thin"), playing: true };
  const next = reduceReplay(
    state,
    { type: "SELECT_PATH_EVENT", presetId: "deep", eventId: "paths.deep.1" },
    index,
  );
  assert.equal(next.presetId, "deep");
  assert.equal(next.eventOrdinal, 1);
  assert.equal(next.playing, false);
  assert.equal(
    reduceReplay(
      state,
      { type: "SELECT_PATH_EVENT", presetId: "deep", eventId: "paths.thin.1" },
      index,
    ),
    state,
  );
});
test("UTC nanoseconds retain the boundary without floating-point rounding", () => {
  const event = path("thin").events[0];
  const before = {
    ...event,
    clock: { ...event.clock, value: "1735689599999999999" },
  };
  const after = {
    ...event,
    clock: { ...event.clock, value: "1735689600000000000" },
  };
  assert.match(recordClock(before, "en"), /07:59:59\.999999999/);
  assert.match(recordClock(after, "en"), /08:00:00/);
});

test("currency units remain explicit and incompatible accounts are not aligned", () => {
  const a = path("thin"),
    b = path("deep");
  b.currency = "USD";
  assert.equal(alignedPathRecord(a, a.events[1], b), null);
  const flow = JSON.parse(
    readFileSync(
      new URL(
        "../../../docs/assets/learning/traces/flow/roundtrip.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  const book = JSON.parse(
    readFileSync(
      new URL(
        "../../../docs/assets/learning/traces/book/depth.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.equal(recordMoneyUnit(flow, "zh-CN"), "USD");
  assert.equal(recordMoneyUnit(book, "zh-CN"), "合成金额单位");
});

test("trial clock labels use the recorded trial number", () => {
  const trace = JSON.parse(
    readFileSync(
      new URL(
        "../../../docs/assets/learning/traces/selection/null-search.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.equal(recordClock(trace.events[5], "zh-CN"), "第 6 组");
});
