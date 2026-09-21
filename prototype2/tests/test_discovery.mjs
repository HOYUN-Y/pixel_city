import test from 'node:test';
import assert from 'node:assert/strict';
import {polygonHit} from '../web/pilot/lab-core.js';
import {validateDense} from '../web/pilot/dense-core.js';
test('polygon hits include boundaries, exclude courtyard, support concavity',()=>{
  const p=[[0,0],[10,0],[10,4],[4,4],[4,10],[0,10]];
  assert.ok(polygonHit(p,{x:2,y:8}));assert.ok(polygonHit(p,{x:4,y:7}));
  assert.equal(polygonHit(p,{x:8,y:8}),false);assert.equal(polygonHit(p,{x:-1,y:0}),false);
});
test('optional static selections reject duplicate ids and malformed polygons',()=>{
  const m={kind:'city-dense-pilot',version:1,width:4608,height:3072,tile_size:512,levels:[.25,.5,1],asset_sha256:{},initialView:{center:[2000,1500],scale:.5}};
  const ids=['gwanghwamun','bosingak','jongno-tower'];
  const o={landmarks:ids.map((id,i)=>({id,rect:[i*100,100,80,80],anchor:[i*100+40,180],occluder_id:id+'-body',reveal_only:id==='bosingak'})),spots:ids.map((id,i)=>({id,xy:[i*100+40,180]})),reveal:{targetId:'bosingak',rect:[90,90,100,100]},route:{points:[{xy:[100,200]},{xy:[200,200]}]},traffic:{focus:[1000,1000],speed:32,lanes:[{start:[100,100],end:[2000,100],offsets:[.15]},{start:[2000,110],end:[100,110],offsets:[.15]}]}};
  validateDense(m,o);
  o.spots.push({id:'test',xy:[10,10],hitPolygon:[[0,0],[20,0],[20,20]]});validateDense(m,o);
  o.spots.push({...o.spots[0]});assert.throws(()=>validateDense(m,o));o.spots.pop();
  o.spots.at(-1).hitPolygon=[[0,0],[1,1],[2,2]];assert.throws(()=>validateDense(m,o));
  o.spots.at(-1).hitPolygon=[[0,0],[5000,0],[0,20]];assert.throws(()=>validateDense(m,o));
  o.spots.at(-1).hitPolygon=undefined;o.spots.at(-1).selectionMode='location-only';validateDense(m,o);
  o.spots.at(-1).hitPolygon=[[0,0],[20,0],[20,20]];assert.throws(()=>validateDense(m,o));
});
