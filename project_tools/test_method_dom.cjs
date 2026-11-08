/* Exercise actual mounted controls and cleanup using a DOM, with fake clocks. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const root=path.resolve(__dirname,'..');
function setup(locale='en') {
 const suffix=locale==='en'?'':'.zh-CN';
 const html=execFileSync('python3',['-c',`import sys;sys.path.insert(0,'project_tools');from method_docs import on_page_markdown;from types import SimpleNamespace;from pathlib import Path;p='backtesting-explained${suffix}.md';print(on_page_markdown(Path('docs',p).read_text(),SimpleNamespace(file=SimpleNamespace(src_uri=p)),None,None))`],{cwd:root,encoding:'utf8'});
 const dom=new JSDOM(html,{runScripts:'outside-only',url:'http://localhost/backtesting-explained/'});
 const w=dom.window;let subscriber;const timers=new Map();let id=0;
 w.setTimeout=fn=>{timers.set(++id,fn);return id};w.clearTimeout=n=>timers.delete(n);
 const media=new w.EventTarget();media.matches=false;w.matchMedia=()=>media;
 let hidden=false;Object.defineProperty(w.document,'hidden',{get:()=>hidden});
 const observers=[];w.IntersectionObserver=class {constructor(callback){this.callback=callback;this.disconnected=false;observers.push(this)}observe(){}disconnect(){this.disconnected=true}};
 w.document$={subscribe:fn=>{subscriber=fn;fn()}};
 w.eval(fs.readFileSync(path.join(root,'docs/javascripts/method-replay.js'),'utf8'));
 return {w,dom,media,timers,observers,revisit:()=>subscriber(),hide:value=>{hidden=value;w.document.dispatchEvent(new w.Event('visibilitychange'))},close:()=>{w.dispatchEvent(new w.Event('pagehide'));w.close()}};
}
function control(scene, action) {return scene.querySelector(`[data-action="${action}"]`)}
test('every scene and selected case has localized summaries and meaningful graphics',()=>{
 for(const locale of ['en','zh-CN']) {
  const app=setup(locale);
  try {
   for(const scene of app.w.document.querySelectorAll('.method-scene')) {
    assert.equal(scene.querySelector('.method-controls').hidden,false);
    const select=scene.querySelector('select');
    for(let index=0;index<select.options.length;index++) {
     select.value=String(index);select.dispatchEvent(new app.w.Event('change'));
     do {
      assert.doesNotMatch(scene.querySelector('svg').textContent,/undefined|NaN|field\.|phase\./);
      assert.doesNotMatch(scene.querySelector('.method-status').textContent,/undefined|NaN|field\.|phase\.|\btrue\b|\bfalse\b/);
      assert.ok(scene.querySelector('tbody tr.method-current'));
      if(control(scene,'step').disabled)break;
      control(scene,'step').click();
     } while(true);
    }
   }
  } finally {app.close()}
 }
});
test('hidden, offscreen, reduced motion and instant revisits stop and dispose mounted behavior',()=>{
 const app=setup();
 try {
  const scene=app.w.document.querySelector('.method-scene');
  const first=scene.querySelector('.method-status').textContent;
  control(scene,'play').click();assert.equal(app.timers.size,1);
  const stale=[...app.timers.values()][0];
  app.hide(true);assert.equal(app.timers.size,0);stale();assert.equal(scene.querySelector('.method-status').textContent,first);
  app.hide(false);assert.equal(app.timers.size,0);
  control(scene,'play').click();app.observers[0].callback([{isIntersecting:false}]);assert.equal(app.timers.size,0);
  app.observers[0].callback([{isIntersecting:true}]);assert.equal(app.timers.size,0);
  app.media.matches=true;app.media.dispatchEvent(new app.w.Event('change'));assert.equal(control(scene,'play').disabled,true);
  control(scene,'step').click();assert.notEqual(scene.querySelector('.method-status').textContent,first);
  app.media.matches=false;app.media.dispatchEvent(new app.w.Event('change'));control(scene,'reset').click();control(scene,'play').click();
  app.revisit();assert.equal(app.timers.size,0);assert.ok(app.observers.slice(0,8).every(o=>o.disconnected));
  assert.equal(scene.querySelector('.method-status').textContent,first);
  control(scene,'step').click();assert.match(scene.querySelector('.method-status').textContent,/Frame 2 \/ 3/);
  control(scene,'reset').click();assert.equal(scene.querySelector('.method-status').textContent,first);
 } finally {app.close()}
});

test('back-forward cache restore remounts disposed controls',()=>{
 const app=setup();try {
  const scene=app.w.document.querySelector('.method-scene');
  app.w.dispatchEvent(new app.w.Event('pagehide'));
  app.w.dispatchEvent(new app.w.PageTransitionEvent('pageshow',{persisted:true}));
  control(scene,'step').click();assert.match(scene.querySelector('.method-status').textContent,/Frame 2 \/ 3/);
 } finally {app.close()}
});
