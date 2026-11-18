// Local build-only mitigation. Never represents an upstream fixed release.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
const manifest = require('../../apps/docs/security/picomatch.json');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const anchor = '  const extglobClose = token => {\n';
const insertion = anchor + "    if (token.type === 'plus' || token.type === 'star') {\n" +
  "      throw new SyntaxError('Repeated extglobs disabled by Engine build security mitigation');\n" +
  "    }\n";

function files(directory, prefix='') {
  return fs.readdirSync(directory,{withFileTypes:true}).flatMap(entry => {
    if(entry.isSymbolicLink()) throw Error('Unexpected package symlink');
    const name=prefix+entry.name;
    return entry.isDirectory()?files(path.join(directory,entry.name),name+'/'):[name];
  }).sort();
}
function verifyPackage(directory, pristine=false) {
  const actual=files(directory);
  if(JSON.stringify(actual)!==JSON.stringify(Object.keys(manifest.files).sort()))
    throw Error('Unexpected picomatch file inventory');
  for(const name of actual) {
    const expected=pristine&&name==='lib/parse.js'?manifest.pristine_parse_sha256:manifest.files[name];
    if(sha(fs.readFileSync(path.join(directory,name)))!==expected)
      throw Error('Unverified picomatch bytes: '+name);
  }
}
function copies(modules, prefix='node_modules') {
  const found=[];
  for(const entry of fs.readdirSync(modules,{withFileTypes:true})) {
    if(entry.name==='.bin'||entry.name.startsWith('.')) continue;
    const full=path.join(modules,entry.name), relative=prefix+'/'+entry.name;
    if(entry.name.startsWith('@')) {
      found.push(...copies(full,relative)); continue;
    }
    if(entry.name==='picomatch') found.push(relative);
    const nested=path.join(full,'node_modules');
    if(fs.existsSync(nested)) found.push(...copies(nested,relative+'/node_modules'));
  }
  return found.sort();
}
function verify(root, patch=false) {
  const lock=JSON.parse(fs.readFileSync(path.join(root,'package-lock.json')));
  const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json')));
  if(pkg.overrides?.picomatch!=='4.0.7') throw Error('Missing exact picomatch override');
  const nodes=Object.keys(lock.packages).filter(n=>n.endsWith('/picomatch')).sort();
  if(nodes.length!==1||nodes[0]!=='node_modules/picomatch'||
     JSON.stringify(nodes)!==JSON.stringify(copies(path.join(root,'node_modules'))))
    throw Error('Installed picomatch inventory differs from lock');
  for(const node of nodes) {
    const item=lock.packages[node];
    if(item.version!=='4.0.7'||item.integrity!==manifest.npm_integrity||item.resolved!==manifest.npm_url)
      throw Error('Unknown picomatch lock identity');
    const directory=path.join(root,node), parser=path.join(directory,'lib/parse.js');
    if(patch&&sha(fs.readFileSync(parser))===manifest.pristine_parse_sha256) {
      verifyPackage(directory,true);
      const original=fs.readFileSync(parser,'utf8');
      if(original.split(anchor).length!==2) throw Error('Unexpected patch anchor');
      const fixed=original.replace(anchor,insertion);
      if(sha(fixed)!==manifest.files['lib/parse.js']) throw Error('Unexpected patched hash');
      fs.writeFileSync(parser,fixed);
    }
    verifyPackage(directory);
  }
  return nodes;
}
function auditResult(report,status,nodes) {
  if(![0,1].includes(status)||!report||report.auditReportVersion!==2||report.error||
     !report.metadata?.vulnerabilities||!report.vulnerabilities||Array.isArray(report.vulnerabilities))
    throw Error('Invalid or unavailable npm audit result');
  const entries=report.vulnerabilities, names=Object.keys(entries);
  if(names.length!==report.metadata.vulnerabilities.total) throw Error('Incomplete audit metadata');
  const visiting=new Set(), done=new Set();
  function visit(name) {
    if(done.has(name)) return;
    if(visiting.has(name)||!entries[name]) throw Error('Unresolved audit chain');
    visiting.add(name);
    const item=entries[name];
    if(item.name!==name||!Array.isArray(item.via)||!item.via.length||!Array.isArray(item.nodes)||!item.nodes.length)
      throw Error('Malformed audit entry');
    for(const via of item.via) {
      if(typeof via==='string') visit(via);
      else if(name!=='picomatch'||via.name!=='picomatch'||via.url!==manifest.advisory||
              via.range!=='<=4.0.7'||via.severity!=='high')
        throw Error('Unmitigated advisory: '+(via?.url||name));
    }
    if(name==='picomatch'&&JSON.stringify([...item.nodes].sort())!==JSON.stringify(nodes))
      throw Error('Audit picomatch inventory differs from patched copies');
    visiting.delete(name); done.add(name);
  }
  names.forEach(visit);
  if((names.length===0&&status!==0)||(names.length>0&&status!==1)) throw Error('Audit exit status mismatch');
  return {unmitigated:0,locally_mitigated_reports:names.length,advisory:manifest.advisory};
}
if(require.main===module) {
  try {
    const mode=process.argv[2], root=path.resolve(process.argv[3]||'apps/docs');
    if(!['patch','verify','audit'].includes(mode)) throw Error('Expected patch, verify or audit');
    const nodes=verify(root,mode==='patch');
    if(mode==='audit') {
      const result=spawnSync('npm',['audit','--json'],{cwd:root,encoding:'utf8',timeout:60000,maxBuffer:8*1024*1024});
      if(result.error) throw result.error;
      if(process.env.FRONTEND_AUDIT_RECEIPT) fs.writeFileSync(process.env.FRONTEND_AUDIT_RECEIPT,result.stdout);
      const report=JSON.parse(result.stdout);
      console.log(JSON.stringify(auditResult(report,result.status,nodes)));
    } else console.log('Verified patched picomatch copies: '+nodes.length);
  } catch(error) { console.error(error.message);process.exitCode=1; }
}
module.exports={verify,verifyPackage,auditResult};
