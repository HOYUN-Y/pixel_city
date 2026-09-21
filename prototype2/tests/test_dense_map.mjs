import test from 'node:test';
import assert from 'node:assert/strict';
import {TileLayer,visibleTiles,safeAsset} from '../web/pilot/tile-layer.js';
import {validateDense,cropHit,intersectRect} from '../web/pilot/dense-core.js';
const m={kind:'city-dense-pilot',version:1,width:4608,height:3072,tile_size:512,levels:[.25,.5,1],preview:'preview.png',asset_sha256:{},initialView:{center:[2000,1500],scale:.5}};
const ids=['gwanghwamun','bosingak','jongno-tower'];
const o={landmarks:ids.map((id,i)=>({id,rect:[i*100,100,80,80],anchor:[i*100+40,180],occluder_id:id+'-body',reveal_only:id==='bosingak'})),spots:ids.map((id,i)=>({id,xy:[i*100+40,180]})),reveal:{targetId:'bosingak',rect:[90,90,100,100]},route:{points:[{xy:[100,200]},{xy:[200,200],behind:['jongno-tower-body']}]},traffic:{focus:[1000,1000],speed:32,lanes:[{start:[100,100],end:[2000,100],offsets:[.15]},{start:[2000,110],end:[100,110],offsets:[.15]}]}};
test('dense contracts isolate the new format and local hit coordinates',()=>{
  assert.equal(validateDense(m,o),o);
  assert.throws(()=>validateDense({...m,width:1792},o));
  assert.throws(()=>validateDense(m,{...o,landmarks:o.landmarks.slice(0,2)}));
  assert.throws(()=>validateDense(m,{...o,reveal:{...o.reveal,rect:[4600,0,20,20]}}));
  const pixels=new Uint8Array(4*4*4);pixels[(2*4+1)*4]=255;
  assert.equal(cropHit({x:101,y:202},[100,200,4,4],pixels),true);
  assert.equal(cropHit({x:99,y:202},[100,200,4,4],pixels),false);
  assert.equal(cropHit({x:104,y:202},[100,200,4,4],pixels),false);
});
test('tile bounds, density and path protection',()=>{
  assert.equal(visibleTiles(m,1,{x:0,y:0,width:4608,height:3072}).length,54);
  assert.equal(visibleTiles(m,.5,{x:0,y:0,width:4608,height:3072}).length,15);
  const edge=visibleTiles(m,.5,{x:4200,y:2500,width:1000,height:1000}).at(-1);
  assert.deepEqual(edge.world,[4096,2048,512,1024]);
  assert.throws(()=>safeAsset('https://example.com/','../secret'));
  assert.throws(()=>safeAsset('https://example.com/','https://evil.com/file'));
});
test('four independent cars, optional polylines and foreground hashes',()=>{
  const overlay=structuredClone(o);
  overlay.traffic.lanes=[...overlay.traffic.lanes,...structuredClone(overlay.traffic.lanes)].map((l,i)=>({...l,id:`region-${i}`,points:[l.start,l.end]}));
  overlay.reveal.foregroundMask='foreground.png';overlay.reveal.auto=true;
  const manifest={...m,asset_sha256:{'foreground.png':'hash'}};
  assert.equal(validateDense(manifest,overlay),overlay);
  assert.throws(()=>validateDense(m,overlay));
  overlay.traffic.lanes[3].id=overlay.traffic.lanes[0].id;
  assert.throws(()=>validateDense(manifest,overlay));
  overlay.traffic.lanes[3].id='unique';overlay.traffic.lanes[0].points=[[0,0],[0,0]];
  assert.throws(()=>validateDense(manifest,overlay));
});
test('traffic masks are optional, lane scoped and hash verified',()=>{
  const item={id:'foreground',rect:[100,100,20,30],mask:'mask.png',lanes:['east']};
  const overlay=structuredClone(o);overlay.traffic.lanes[0].id='east';overlay.traffic.lanes[1].id='west';overlay.traffic.occluders=[item];
  const manifest={...m,asset_sha256:{'mask.png':'abc'}};
  assert.equal(validateDense(manifest,overlay),overlay);
  assert.throws(()=>validateDense(m,overlay));
  for(const change of [{rect:[4600,0,20,20]},{lanes:['missing']},{mask:'../mask.png'}]){
    assert.throws(()=>validateDense(manifest,{...overlay,traffic:{...overlay.traffic,occluders:[{...item,...change}]}}));
  }
  assert.deepEqual(intersectRect([0,0,10,10],[5,6,10,10]),[5,6,5,4]);
  assert.equal(intersectRect([0,0,10,10],[10,0,10,10]),null);
});
test('tile cache stays bounded, stale loads close, failed requests keep preview and never loop',async()=>{
  let active=0,max=0,closed=0,calls=0;
  const picture=async(base,file)=>{active++;calls++;max=Math.max(max,active);await new Promise(r=>setTimeout(r,1));active--;if(file==='preview.png')return{width:1152,height:768,close(){closed++;}};const [,level,xy]=file.split('/'),[x,y]=xy.replace('.png','').split('_').map(Number),l=Number(level);return{width:Math.min(512,m.width*l-x*512),height:Math.min(512,m.height*l-y*512),close(){closed++;}};};
  const tiles=new TileLayer(m,'https://example.com/',()=>{},picture);await tiles.init();
  const settle=async()=>{for(let i=0;i<100&&tiles.pending.size;i++)await new Promise(r=>setTimeout(r,3));assert.equal(tiles.pending.size,0);};
  tiles.request({x:0,y:0,width:1440,height:1000},1);
  tiles.request({x:3168,y:2072,width:1440,height:1000},1);await settle();
  for(let x=0;x<4608;x+=768){tiles.request({x,y:0,width:1440,height:3072},1);await settle();assert.ok(tiles.cache.size<=48);}
  assert.ok(max<=4);assert.ok(closed>0);const before=calls;tiles.request({x:0,y:0,width:4608,height:3072},.25);await settle();assert.equal(calls,before);
  tiles.picture=async()=>{throw Error('offline');};tiles.cache.forEach(im=>im.close());tiles.cache.clear();tiles.request({x:0,y:0,width:1440,height:1000},1);await settle();assert.ok(tiles.preview);assert.ok(tiles.failed.size>0);
  const failedCount=tiles.requests;tiles.request({x:0,y:0,width:1440,height:1000},1);await settle();assert.equal(tiles.requests,failedCount);tiles.close();assert.equal(tiles.cache.size,0);
});
