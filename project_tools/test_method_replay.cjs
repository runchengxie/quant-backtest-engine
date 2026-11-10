const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = path.resolve(__dirname, '../docs/javascripts/method-replay.js');
test('replay implementation exists', () => assert.ok(fs.existsSync(source), 'replay lifecycle is missing'));
if (fs.existsSync(source)) {
 const {Playback, translate} = require(source);
 function setup(reduced=false) {
  let callback, removed=0, drawn=[];
  const p = new Playback(3, n=>drawn.push(n), {reduced, schedule: cb => {callback=cb;return 17;}, cancel: () => {removed++;}});
  return {p, drawn, tick:()=>callback(), removed:()=>removed};
 }
 test('motion is opt-in; step, reset and final frame are exact', ()=>{
  const a=setup(); assert.equal(a.p.playing,false); assert.deepEqual(a.drawn,[0]);
  a.p.step(); assert.deepEqual(a.drawn,[0,1]); a.p.reset(); assert.equal(a.drawn.at(-1),0);
  a.p.play(); a.tick(); assert.equal(a.drawn.at(-1),1); a.tick(); assert.equal(a.drawn.at(-1),2); assert.equal(a.p.playing,false);
 });
 test('hidden/offscreen pause never resumes without consent',()=>{
  const a=setup(); a.p.play(); a.p.visibility(false); assert.equal(a.p.playing,false); a.tick(); assert.equal(a.drawn.at(-1),0);
  a.p.visibility(true); assert.equal(a.p.playing,false);
 });
 test('reduced motion stays manual and lifecycle disposal cancels stale ticks',()=>{
  const a=setup(true); a.p.play(); assert.equal(a.p.playing,false); a.p.step(); assert.equal(a.drawn.at(-1),1);
  const b=setup(); b.p.play(); b.p.dispose(); b.tick(); assert.equal(b.drawn.at(-1),0); assert.ok(b.removed()>0);
 });
 test('locale keys fallback to English',()=> assert.equal(translate({play:'Play'}, {}, 'play'),'Play'));
}
