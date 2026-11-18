import test from "node:test";
import assert from "node:assert/strict";
import {
  initialState,
  reduceReplay,
  comparisonEvents,
} from "../src/lib/replay-state.ts";
import { readFileSync } from "node:fs";
const read = (p: string) =>
  JSON.parse(
    readFileSync(
      new URL(
        "../../docs/assets/learning/traces/" + p + ".json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
const traces = ["thin", "deep", "market-up", "feedback"].map((p) =>
  read("paths/" + p),
);
const index = new Map(traces.map((t) => [t.preset_id, t]));
test("bounds, explicit seeks, final playback, reset and reduced motion", () => {
  let s = initialState("thin");
  s = reduceReplay(s, { type: "PREVIOUS" }, index);
  assert.equal(s.eventOrdinal, 0);
  s = reduceReplay(s, { type: "PLAY" }, index);
  assert.equal(s.playing, true);
  s = reduceReplay(s, { type: "NEXT" }, index);
  assert.equal(s.playing, false);
  for (let i = 0; i < 20; i++) s = reduceReplay(s, { type: "NEXT" }, index);
  assert.equal(s.eventOrdinal, traces[0].events.length - 1);
  s = reduceReplay(s, { type: "PLAY" }, index);
  assert.equal(s.playing, true);
  s = reduceReplay(s, { type: "TICK" }, index);
  assert.equal(s.eventOrdinal, 0);
  assert.equal(s.playing, true);
  s = reduceReplay(s, { type: "SET_SPEED", speed: 2 }, index);
  assert.equal(s.playing, false);
  assert.equal(s.speed, 2);
  s = reduceReplay(s, { type: "PAUSE" }, index);
  assert.equal(reduceReplay(s, { type: "TICK" }, index).eventOrdinal, 0);
  s = reduceReplay(s, { type: "RESET" }, index);
  assert.equal(s.eventOrdinal, 0);
  s = reduceReplay(s, { type: "SET_REDUCED_MOTION", value: true }, index);
  assert.equal(reduceReplay(s, { type: "PLAY" }, index).playing, false);
  assert.deepEqual(
    reduceReplay(s, { type: "SELECT_EVENT", eventId: "bad" }, index),
    s,
  );
});
test("comparison always reads its own account and missing means null", () => {
  let s = reduceReplay(
    initialState("thin"),
    { type: "SET_COMPARISON", presetIds: ["deep"] },
    index,
  );
  s = reduceReplay(
    s,
    { type: "SELECT_EVENT", eventId: traces[0].events.at(-1).event_id },
    index,
  );
  const row = comparisonEvents(s, index)[0];
  assert.equal(row.event?.event_id, traces[1].events.at(-1).event_id);
  assert.notEqual(row.event?.values.cash, traces[0].events.at(-1).values.cash);
});
