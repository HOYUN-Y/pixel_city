// Canvas/browser contract tests; these do not substitute for visual browser QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(require('node:path').join(__dirname, '../web/app.js'), 'utf8');
async function boot(manifest, hash = '') {
  const nodes = new Map();
  const context = new Proxy({}, {get: (o,k)=>o[k] || (()=>{})});
  const node = () => ({value:'',children:[],classList:{add(){},remove(){}},getContext:()=>context,
    setPointerCapture(){},append(v){this.children.push(v)},remove(){}});
  const sandbox = {document:{querySelector(key){if(!nodes.has(key))nodes.set(key,node());return nodes.get(key)},createElement:node},
    innerWidth:1000,innerHeight:700,devicePixelRatio:1,addEventListener(){},
    location:{hash},history:{replaceState(a,b,h){sandbox.location.hash=h}},
    Image:class {complete=false; naturalWidth=0},
    fetch:async url=>({ok:true,json:async()=>url.includes('manifest')?manifest:
      {museum:[],market:[],tourinfo:[],subway:{stations:[]}}})};
  vm.createContext(sandbox);vm.runInContext(code,sandbox);
  await new Promise(r=>setImmediate(r));
  return {sandbox,nodes,run:s=>vm.runInContext(s,sandbox)};
}
(async()=>{
  const base={width:9134,height:5528,max_zoom:6,tile_size:256};
  const legacy=await boot({...base});
  assert.equal(legacy.run('style'),'baseline');
  assert.equal(legacy.nodes.get('#style').disabled,true);
  const v=await boot({...base,styles:{baseline:'tiles',diorama:'tiles/diorama'},default_style:'diorama'});
  assert.equal(v.run('tileUrl(2,3)'),'tiles/diorama/4/2/3.png');
  const anchor=v.run('JSON.stringify([cx,cy,z])');
  v.run("selectStyle('baseline')");
  assert.equal(v.run('JSON.stringify([cx,cy,z])'),anchor);
  assert.ok(v.sandbox.location.hash.endsWith(',baseline'));
  const world=v.run('cx/scale()');v.run('setZoom(5)');assert.equal(v.run('cx/scale()'),world);
  const canvas=v.nodes.get('#map');canvas.onpointerdown({clientX:50,clientY:50,pointerId:1});
  const old=v.run('cx');canvas.onpointermove({clientX:80,clientY:50});assert.equal(v.run('cx'),old-30);
  canvas.onpointerup();assert.equal(v.run('drag'),null);
  v.nodes.get('#poi').onchange({target:{checked:false}});assert.equal(v.run('showPoi'),false);
  const restored=await boot({...base,styles:{baseline:'tiles',diorama:'tiles/diorama'}},'#5,2000,1000,diorama');
  assert.equal(restored.run('style'),'diorama');assert.equal(restored.run('z'),5);
  const bounded=await boot({...base},'#999,200,200,diorama');assert.equal(bounded.run('z'),6);
  assert.equal(bounded.run('style'),'baseline');
  console.log('Viewer contracts passed: legacy manifest, style switch, zoom, pan, POI, URL restore');
})().catch(e=>{console.error(e);process.exitCode=1});
