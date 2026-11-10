/* Owner-state replay only. No matching, portfolio optimization or cash model. */
(function (global) {
  'use strict';
  class Playback {
    constructor(length, draw, options = {}) {
      this.length = length; this.draw = draw; this.index = 0;
      this.playing = false; this.visible = true; this.disposed = false;
      this.reduced = options.reduced || false;
      this.schedule = options.schedule || (fn => setTimeout(fn, 1200));
      this.cancel = options.cancel || clearTimeout;
      this.changed = options.changed || (() => {});
      this.timer = null; this.generation = 0; this.draw(0);
    }
    pause() {
      this.playing = false; this.generation += 1;
      if (this.timer !== null) this.cancel(this.timer);
      this.timer = null; this.changed(this);
    }
    play() {
      if (this.disposed || this.reduced || !this.visible || this.playing || this.index >= this.length - 1) return;
      this.playing = true; this.changed(this); this.queue();
    }
    queue() {
      const generation = this.generation;
      this.timer = this.schedule(() => {
        if (this.disposed || !this.playing || generation !== this.generation) return;
        this.index += 1; this.draw(this.index);
        if (this.index >= this.length - 1) this.pause(); else this.queue();
      });
    }
    step() {
      if (this.disposed) return;
      this.pause(); this.index = Math.min(this.index + 1, this.length - 1); this.draw(this.index);
    }
    reset() { if (!this.disposed) {this.pause(); this.index = 0; this.draw(0);} }
    visibility(visible) { this.visible = visible; if (!visible) this.pause(); }
    motion(reduced) { this.reduced = reduced; if (reduced) this.pause(); this.changed(this); }
    dispose() { this.pause(); this.disposed = true; }
  }
  function translate(english, locale, key) { return locale[key] ?? english[key] ?? key; }
  if (typeof module !== 'undefined' && module.exports) module.exports = {Playback, translate};
  if (!global.document || global.__methodReplay) return;
  global.__methodReplay = true;
  const doc = global.document;
  const ns = 'http://www.w3.org/2000/svg';
  let cleanups = [];
  function node(tag, attrs = {}, text) {
    const element = doc.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, String(value)));
    if (text !== undefined) element.textContent = String(text);
    return element;
  }
  function graphic(svg, scene, scenario, index, t) {
    svg.replaceChildren();
    const rows = scenario.states, row = rows[index];
    const put = (tag, attrs, text) => svg.appendChild(node(tag, attrs, text));
    const label = (x,y,text,attrs={}) => put('text',{x,y,...attrs},text);
    const line = (x1,y1,x2,y2) => put('line',{x1,y1,x2,y2,class:'method-line'});
    const box = (x,y,width,height,active=false) => put('rect',{x,y,width,height,rx:8,class:active?'method-shape method-active':'method-shape'});
    label(18,25,t('visual.'+scene),{class:'method-svg-title'});
    if (scene === 'impact') {
      const max = Math.max(.01,...rows.map(r=>Number(r.transient)+Number(r.permanent)));
      const x = i=>40+i*140, y=v=>170-120*v/max;
      line(40,170,460,170);
      [['unaffected',()=>0],['transient',r=>Number(r.transient)],['permanent',r=>Number(r.permanent)]].forEach(([key,value],series)=>{
        put('polyline',{points:rows.map((r,i)=>`${x(i)},${y(value(r))}`).join(' '),class:`method-series method-series-${series}`});
        put('circle',{cx:x(index),cy:y(value(row)),r:6,class:`method-point method-series-${series}`});
        label(32+series*160,204,t('field.'+key),{class:`method-legend method-series-${series}`});
      });
      label(40,233,t('diagram.elapsed')+' '+row.clock+' s');
    } else if (scene === 'book') {
      [[99,100],[101,5],[110,10]].forEach(([price,depth],i)=>{
        label(25,65+i*48,String(price));
        const remaining=i===0?depth:Math.max(0,depth-(i===1?Math.min(Number(row.quantity),5):Math.max(0,Number(row.quantity)-5)));
        box(85,43+i*48,Math.max(4,depth*3),30);
        put('rect',{x:85,y:43+i*48,width:Math.max(2,remaining*3),height:30,rx:6,class:'method-fill'});
        label(405,64+i*48,String(remaining));
      });
      label(25,221,t('field.reported')+' '+row.reported+' / '+row.quantity);
    } else if (scene === 'lots') {
      const chosen=row.shares;
      scenario.grid.forEach(cell=>{
        const [a,b]=cell.shares.split(',').map(Number), x=90+a*90,y=190-b*42;
        put('circle',{cx:x,cy:y,r:14,class:cell.feasible?'method-feasible':'method-infeasible'});
        if(cell.shares===chosen) put('circle',{cx:x,cy:y,r:20,class:'method-ring'});
        label(x,y+4,cell.shares,{'text-anchor':'middle',class:'method-grid-label'});
      });
      label(28,239,t('diagram.grid'));
    } else if (scene === 'selection') {
      line(35,132,475,132);
      rows.forEach((r,i)=>{
        const value=Number(r.score), height=Math.abs(value)*4800;
        put('rect',{x:48+i*70,y:value>=0?132-height:132,width:36,height:Math.max(3,height),class:i===index?'method-fill':'method-shape',opacity:i<=index?1:.25});
        label(66+i*70,229,String(i+1),{'text-anchor':'middle'});
        if(r.selected && i<=index) put('circle',{cx:66+i*70,cy:45,r:12,class:'method-ring'});
      });
      label(30,253,t('diagram.trials'));
    } else if (scene === 'risk' && scenario.id.startsWith('risk-')) {
      const keys=['predicted_variance','realized_squared_residual'];
      const maximum=Math.max(1,...rows.flatMap(r=>keys.map(k=>Number(r[k]??0))));
      keys.forEach((key,i)=>{
        label(25,65+i*74,t('field.'+key));
        if(row[key]===null) label(25,91+i*74,t('value.unknown'));
        else {
          box(25,77+i*74,365,25);
          put('rect',{x:25,y:77+i*74,width:Math.max(2,365*Number(row[key])/maximum),height:25,rx:6,class:'method-fill'});
          label(410,96+i*74,row[key]);
        }
      });
      label(25,231,t('phase.'+row.phase));
    } else if (scene === 'risk' && scenario.id === 'shared') {
      box(20,55,135,45,index===0); box(20,145,135,45,index===0);
      label(35,84,t('diagram.sleeve')+' A'); label(35,174,t('diagram.sleeve')+' B');
      line(155,78,255,120);line(155,168,255,120);box(255,97,220,54,index>0);
      label(269,129,t('field.quantity')+' '+row.quantity);
      label(30,232,t('diagram.onebudget'));
    } else if (scene === 'cost') {
      [['cash',row.cash],['gross',row.gross],['fees',row.fees]].forEach(([key,value],i)=>{
        box(25+i*160,66,142,75,index>0);label(38+i*160,93,t('field.'+key));label(38+i*160,122,value);
      });
      label(30,190,t('diagram.embedded'));
      label(30,224,t('field.impact_cost')+' '+row.impact_cost);
    } else if (scene === 'paths') {
      [['cash',row.cash,10000],['quantity',row.quantity,1000]].forEach(([key,value,max],i)=>{
        label(25,69+i*65,t('field.'+key)+' '+value);
        box(195,43+i*65,280,35);
        put('rect',{x:195,y:43+i*65,width:Math.max(2,280*Number(value)/max),height:35,rx:6,class:'method-fill'});
      });
      label(30,205,t('field.next_target')+' '+(row.next_target??t('value.unknown')));
      put('path',{d:'M 475 160 Q 480 245 220 240 Q 20 240 20 175',class:'method-feedback'});
    } else {
      const labels=scene==='flow'?['forecast','buy','sell']:rows.map(r=>r.phase);
      labels.slice(0,7).forEach((key,i)=>{
        const count=Math.min(labels.length,7), width=440/count,x=30+i*width;
        box(x,80,width-12,63,i===index);label(x+8,115,t('phase.'+key));
        if(i<count-1)line(x+width-12,111,x+width,111);
      });
      label(30,195,t('field.cash')+' '+row.cash);
      label(30,229,t('field.quantity')+' '+row.quantity);
    }
    // The moving marker advances between exported events; it changes no finance.
    put('circle',{cx:25+450*index/Math.max(1,rows.length-1),cy:277,r:6,class:'method-cursor'});
    line(25,277,475,277);
  }
  function mount(root) {
    const payload = JSON.parse(root.querySelector('.method-payload').textContent);
    const t = key => translate(payload.english,payload.locale,key);
    const media = global.matchMedia('(prefers-reduced-motion: reduce)');
    const abort = new AbortController();
    let playback, selected=0, offscreen=false;
    const controls = root.querySelector('.method-controls');
    const select = controls.querySelector('select');
    const play = controls.querySelector('[data-action="play"]');
    const step = controls.querySelector('[data-action="step"]');
    const status = root.querySelector('.method-status');
    const svg = root.querySelector('svg');
    function stateChanged(p) {
      play.textContent=t(p.playing?'pause':'play');
      play.disabled=p.reduced || p.index===p.length-1;
      play.setAttribute('aria-pressed',String(p.playing));
      step.disabled=p.index===p.length-1;
      root.classList.toggle('method-playing',p.playing);
    }
    function choose() {
      if(playback)playback.dispose();
      const scenario=payload.scene.scenarios[selected];
      root.querySelectorAll('.method-case').forEach(details=>{details.open=details.dataset.methodCase===scenario.id;});
      playback=new Playback(scenario.states.length,index=>{
        graphic(svg,payload.id,scenario,index,t);
        const state=scenario.states[index];
        status.textContent=t('frame')+' '+(index+1)+' / '+scenario.states.length+' · '+t('phase.'+state.phase)+' · '+
          Object.entries(state).filter(([key])=>!['phase','selected','report_pending'].includes(key)).map(([key,value])=>t('field.'+key)+' '+(value===null?t('value.unknown'):typeof value==='boolean'?t('value.'+String(value)):String(value))).join(' · ');
        root.querySelectorAll('tbody tr').forEach(row=>row.classList.toggle('method-current',row.dataset.scenario===scenario.id&&Number(row.dataset.frame)===index));
      },{reduced:media.matches,changed:stateChanged});
      playback.visibility(!doc.hidden&&!offscreen);stateChanged(playback);
    }
    controls.hidden=false; root.querySelector('.method-stage').hidden=false;
    controls.addEventListener('click',event=>{
      const action=event.target.closest('button')?.dataset.action;
      if(action==='play')playback.playing?playback.pause():playback.play();
      if(action==='step')playback.step();
      if(action==='reset')playback.reset();
      stateChanged(playback);
    },{signal:abort.signal});
    select.addEventListener('change',()=>{selected=Number(select.value);choose();},{signal:abort.signal});
    doc.addEventListener('visibilitychange',()=>playback.visibility(!doc.hidden&&!offscreen),{signal:abort.signal});
    const motion=()=>playback.motion(media.matches);
    media.addEventListener('change',motion);
    const observer=new IntersectionObserver(entries=>{
      offscreen=!entries[0].isIntersecting; playback.visibility(!doc.hidden&&!offscreen);
    });
    choose();observer.observe(root);
    return ()=>{playback.dispose();abort.abort();observer.disconnect();media.removeEventListener('change',motion);};
  }
  function initialize() {
    cleanups.forEach(cleanup=>cleanup());cleanups=[];
    doc.querySelectorAll('.method-scene').forEach(root=>cleanups.push(mount(root)));
  }
  if(global.document$)global.document$.subscribe(initialize);
  else if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
  global.addEventListener('pageshow',event=>{if(event.persisted)initialize();});
  global.addEventListener('pagehide',()=>{cleanups.forEach(cleanup=>cleanup());cleanups=[];});
})(typeof window !== 'undefined' ? window : globalThis);
