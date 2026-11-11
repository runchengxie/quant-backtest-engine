import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { initialState, reduceReplay } from "../src/lib/replay-state.ts";
test("preset/comparison changes reset and pause; unknown events preserve the exact cursor", () => {
  const traces = ["small", "large"].map((p) =>
    JSON.parse(
      readFileSync(
        new URL(
          "../../docs/assets/learning/traces/impact/" + p + ".json",
          import.meta.url,
        ),
        "utf8",
      ),
    ),
  );
  const index = new Map(traces.map((t) => [t.preset_id, t]));
  let state = reduceReplay(initialState("small"), { type: "PLAY" }, index);
  state = reduceReplay(
    state,
    { type: "SELECT_PRESET", presetId: "large" },
    index,
  );
  assert.equal(state.eventOrdinal, 0);
  assert.equal(state.playing, false);
  state = reduceReplay(state, { type: "NEXT" }, index);
  state = reduceReplay(
    state,
    { type: "SET_COMPARISON", presetIds: ["small"] },
    index,
  );
  assert.equal(state.eventOrdinal, 0);
  assert.equal(state.playing, false);
  assert.deepEqual(
    reduceReplay(
      state,
      { type: "SELECT_EVENT", eventId: "not-recorded" },
      index,
    ),
    state,
  );
});
