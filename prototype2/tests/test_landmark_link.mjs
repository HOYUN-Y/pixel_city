import assert from 'node:assert/strict';
import {labSize} from '../web/pilot/lab-size.js';
import {shadowTransform,validateSunset} from '../web/pilot/sunset.js';
import {validateLiving,vehiclePosition} from '../web/pilot/living-core.js';
assert.deepEqual(labSize({width:1792,height:1024}),{width:1792,height:1024});
assert.throws(()=>labSize({width:1792,height:1792}));
for(const n of [1024,1536,2304])assert.equal(labSize({width:n,height:n}).height,n);
const s={kind:'ground-alpha-preview',anchor:[1275,608],height:174,direction:[.8,.6],receiver:'receiver.png'};
validateSunset(s,{width:1792,height:1024});
assert.throws(()=>validateSunset({...s,direction:[1,1]},{width:1792,height:1024}));
assert.throws(()=>shadowTransform(s,NaN));assert.throws(()=>shadowTransform(s,2));
for(const a of [0,.5,1]){const [xx,xy,yx,yy,tx,ty]=shadowTransform(s,a);assert.ok(Math.abs(xx*1275+yx*608+tx-1275)<1e-6);assert.ok(Math.abs(xy*1275+yy*608+ty-608)<1e-6);}
const lane={id:'east',start:[710,192],end:[1000,280],offsets:[0],sprite:'car.png'};
validateLiving({traffic:{speed:20,lanes:[lane,{...lane,id:'west',start:lane.end,end:lane.start}],occluders:[]}}, {width:1792,height:1024});
assert.ok(vehiclePosition(lane,5,0,20).xy[0]>768);
console.log('Link: rectangular size, affine ground anchor, sunset limits, two-car lanes passed');
