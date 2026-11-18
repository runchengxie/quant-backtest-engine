import { test } from "node:test";
import assert from "node:assert/strict";
import {
  geometryValue,
  relativeWidth,
  teachingText,
} from "../src/lib/teaching-catalog.ts";
test("unknown, booleans and invalid numeric values never become zero geometry", () => {
  for (const value of [
    null,
    undefined,
    true,
    false,
    "",
    "NaN",
    "Infinity",
    "1,2",
  ])
    assert.equal(geometryValue(value), null);
  assert.equal(geometryValue("0"), 0);
  assert.equal(relativeWidth(null, 20), null);
  assert.equal(relativeWidth("5", 20), 25);
});
test("semantic catalogs have Chinese coverage and English fallback", () => {
  assert.equal(
    teachingText("fr", "flow.title"),
    teachingText("en", "flow.title"),
  );
  assert.notEqual(
    teachingText("zh-CN", "flow.title"),
    teachingText("en", "flow.title"),
  );
});

test("signed opportunity geometry preserves sign and unknowns without financial arithmetic", async () => {
  const { signedGeometry } = await import("../src/lib/teaching-catalog.ts");
  assert.deepEqual(signedGeometry("-200", 200), { x: 0, width: 50 });
  assert.deepEqual(signedGeometry("0", 200), { x: 50, width: 0 });
  assert.deepEqual(signedGeometry("200", 200), { x: 50, width: 50 });
  assert.equal(signedGeometry(null, 200), null);
  assert.equal(signedGeometry("200", 0), null);
});
