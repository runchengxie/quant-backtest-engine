import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { LearningTrace } from "../src/lib/trace-schema.ts";
import { recordedPathGeometry } from "../src/lib/path-geometry.ts";
const paths = () => ["thin", "deep", "market-up", "feedback"].map(id => JSON.parse(readFileSync(new URL(`../../../docs/assets/learning/traces/paths/${id}.json`,import.meta.url),"utf8")) as LearningTrace);

test("all recorded paths share holdings and exact elapsed-time scales", () => {
  const traces=paths();const value=recordedPathGeometry(traces[0],traces);
  assert.ok(value);assert.equal(value.maximum,1000);
  assert.deepEqual(value.paths.get("deep")?.map(p=>p.y),[80,50,20]);
  assert.deepEqual(value.paths.get("thin")?.map(p=>p.y),[80,74,68]);
  assert.equal(value.x[0],12);assert.equal(value.x[2],88);
  assert.ok(Math.abs(value.x[1]-(12+76*4/7))<1e-10);
});

test("missing, unsafe or differently defined observations retain the non-quantitative fallback", () => {
  for(const mutate of [
    (t:LearningTrace[])=>{t[1].events[1].values.quantity=null;},
    (t:LearningTrace[])=>{t[1].events[1].values.quantity="9007199254740993";},
    (t:LearningTrace[])=>{t[1].units.quantity="lots";},
    (t:LearningTrace[])=>{t[1].currency="USD";},
    (t:LearningTrace[])=>{t[1].events[1].clock.value="1";},
    (t:LearningTrace[])=>{t[1].events.pop();},
  ]) {const traces=paths();mutate(traces);assert.equal(recordedPathGeometry(traces[0],traces),null);}
});
