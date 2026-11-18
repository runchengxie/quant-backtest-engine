import test from "node:test";
import assert from "node:assert/strict";
import {motionText,motionCaptionKey} from "../src/lib/motion-catalog.ts";
test("step explanations use the recorded stage and preserve locale fallback",()=>{
  assert.equal(motionCaptionKey("book","report"),"caption.book.report");
  assert.equal(motionCaptionKey("selection","trial"),"caption.selection");
  const values={reported:"15",quantity:"15"};
  assert.equal(motionText("fr","caption.book.report",values),motionText("en","caption.book.report",values));
  const chinese=motionText("zh-CN","caption.book.report",values);
  assert.ok(chinese.includes("15"));
  assert.ok(!/[：:；;“”—–]/.test(chinese));
});
