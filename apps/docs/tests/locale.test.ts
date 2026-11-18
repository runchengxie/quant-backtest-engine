import test from "node:test";
import assert from "node:assert/strict";
import {
  savedLocale,
  persistLocale,
  pairedRoute,
  translate,
} from "../src/lib/locale.ts";
test("English default, blocked storage, missing message and explicit paired routes", () => {
  assert.equal(savedLocale(undefined), "en");
  assert.equal(
    savedLocale({
      getItem() {
        throw Error();
      },
    }),
    "en",
  );
  persistLocale(
    {
      setItem() {
        throw Error();
      },
    },
    "zh-CN",
  );
  assert.equal(translate({}, { hello: "Hello" }, "hello"), "Hello");
  assert.equal(
    pairedRoute("learn/impact/", "zh-CN", {
      "learn/impact/": "learn/zh-CN/impact/",
    }),
    "learn/zh-CN/impact/",
  );
});
