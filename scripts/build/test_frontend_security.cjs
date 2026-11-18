const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '../../apps/docs');
const {auditResult,verifyPackage,verify}=require('./frontend_security.cjs');
const advisory='https://github.com/advisories/GHSA-fc5q-39xc-vjpf';
const nodes=['node_modules/picomatch'];
function report() {
  return {auditReportVersion:2,metadata:{vulnerabilities:{total:2}},vulnerabilities:{
    picomatch:{name:'picomatch',nodes,via:[{name:'picomatch',url:advisory,range:'<=4.0.7',severity:'high'}]},
    astro:{name:'astro',nodes:['node_modules/astro'],via:['picomatch']}
  }};
}
test('audit admits only the patched advisory and complete transitive chains',()=>{
  assert.equal(auditResult(report(),1,nodes).locally_mitigated_reports,2);
  for(const mutate of [
    r=>r.vulnerabilities.picomatch.via[0].url='https://example.com/new',
    r=>r.vulnerabilities.astro.via=['missing'],
    r=>r.vulnerabilities.astro.via=['astro'],
    r=>r.vulnerabilities.picomatch.nodes.push('node_modules/hidden/picomatch'),
    r=>r.metadata.vulnerabilities.total=0,
    r=>r.error={code:'NETWORK'},
    r=>r.auditReportVersion=1
  ]) { const r=report();r.vulnerabilities.picomatch.nodes=[...nodes];mutate(r);assert.throws(()=>auditResult(r,1,nodes)); }
  for(const status of [0,2,null]) assert.throws(()=>auditResult(report(),status,nodes));
});
test('any modified package entrypoint invalidates the mitigation',()=>{
  const fs=require('node:fs'),os=require('node:os');
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'engine-picomatch-'));
  try {fs.cpSync(path.join(root,'node_modules/picomatch'),temp,{recursive:true});verifyPackage(temp);
    fs.appendFileSync(path.join(temp,'index.js'),'\n// tampered');assert.throws(()=>verifyPackage(temp),/Unverified/);
  } finally {fs.rmSync(temp,{recursive:true});}
});
test('unknown lock versions and unregistered installed copies stop admission',()=>{
  const fs=require('node:fs'),os=require('node:os');
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'engine-lock-'));
  try {
    fs.mkdirSync(path.join(temp,'node_modules'));
    fs.cpSync(path.join(root,'node_modules/picomatch'),path.join(temp,'node_modules/picomatch'),{recursive:true});
    fs.copyFileSync(path.join(root,'package.json'),path.join(temp,'package.json'));
    const lock=JSON.parse(fs.readFileSync(path.join(root,'package-lock.json')));
    const write=()=>fs.writeFileSync(path.join(temp,'package-lock.json'),JSON.stringify(lock));
    write();assert.deepEqual(verify(temp),nodes);
    lock.packages['node_modules/picomatch'].version='4.0.6';write();assert.throws(()=>verify(temp),/lock identity/);
    lock.packages['node_modules/picomatch'].version='4.0.7';write();
    fs.mkdirSync(path.join(temp,'node_modules/extra/node_modules'),{recursive:true});
    fs.cpSync(path.join(root,'node_modules/picomatch'),path.join(temp,'node_modules/extra/node_modules/picomatch'),{recursive:true});
    assert.throws(()=>verify(temp),/inventory/);
  } finally {fs.rmSync(temp,{recursive:true});}
});

test('repeated extglob compilation is blocked through public APIs and option variants', () => {
  const script = `
    const assert=require('node:assert/strict');
    const pm=require(${JSON.stringify(path.join(root,'node_modules/picomatch'))});
    for(const pattern of ['+(*)','+(*a)','*(a*)','+(*a|b)','+(ab|abab)','+(+(a))','x/+(*a).md'])
      for(const options of [{},{capture:true},{maxExtglobRecursion:false},{fastpaths:false}])
        for(const compile of [pm,pm.makeRe,pm.parse])
          assert.throws(()=>compile(pattern,options), /Repeated extglobs disabled/);
    assert.equal(pm('**/*.{md,mdx}')('guide/topic.md'),true);
    assert.equal(pm('**/*.{md,mdx}')('guide/topic.js'),false);
    assert.equal(pm('@(a|b).md')('a.md'),true);
    assert.equal(pm('file-?.md')('file-a.md'),true);
    assert.equal(pm('literal\\\\+\\\\(a\\\\).md')('literal+(a).md'),true);
  `;
  const result = spawnSync(process.execPath, ['-e', script], {timeout:3000,encoding:'utf8'});
  assert.ifError(result.error);
  assert.equal(result.status,0,result.stderr);
});
