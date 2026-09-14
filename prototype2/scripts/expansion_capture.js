// In-memory VWorld page only. Camera coordinates come from the pinned probe.
const exp=window.__expand={ready:true};
const vec=a=>new C.Cartesian3(...a),arr=v=>[v.x,v.y,v.z];
const add=(a,b,s)=>C.Cartesian3.add(a,C.Cartesian3.multiplyByScalar(b,s,new C.Cartesian3()),new C.Cartesian3());
const direction=vec(BASE.direction),up=vec(BASE.up),right=C.Cartesian3.cross(direction,up,new C.Cartesian3());
const origin=vec(BASE.position),position=add(add(origin,right,-300),up,700/3);
const expected={position:arr(position),direction:BASE.direction,up:BASE.up};
const anchors=[];
// Project the same world points into parent and expanded pixel grids.
for(const depth of [1000,1800,2600])for(const [x,y] of [[200,300],[768,768],[1250,1300]]){
  anchors.push({world:add(add(add(origin,direction,depth),right,(x-768)*1600/1536),up,(768-y)*1600/1536),xy:[x+480,y+416]});
}
// Warm the SDK's building cache through its usual perspective camera first.
// Only the final orthographic view is an input; the warm-up is never captured.
exp.warm=async(xy=[1152,1152])=>{
  exp.prepare();
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  const ray=viewer.camera.getPickRay(new C.Cartesian2((xy[0]+128)*.75,(xy[1]+128)*.75));
  const target=viewer.scene.globe.pick(ray,viewer.scene);
  if(!target)throw Error('Warmup ground point unavailable');
  viewer.camera.lookAt(target,new C.HeadingPitchRange(C.Math.toRadians(22.5),C.Math.toRadians(-30),900));
  const f=new C.PerspectiveFrustum();f.aspectRatio=1;f.fov=Math.PI/3;f.near=1;f.far=10000;
  viewer.camera.frustum=f;viewer.scene.requestRender();
};
exp.prepare=()=>{
  viewer.camera.lookAtTransform(C.Matrix4.IDENTITY);
  viewer.camera.setView({destination:position,orientation:{direction,up},endTransform:C.Matrix4.IDENTITY});
  const f=new C.OrthographicFrustum();f.aspectRatio=1;f.width=2000;f.near=1;f.far=10000;viewer.camera.frustum=f;
  document.querySelector('#state').style.display='none';viewer.scene.requestRender();
};
exp.measure=()=>{
  const camera=viewer.camera,f=camera.frustum,m=f.projectionMatrix;
  const project=C.SceneTransforms.worldToWindowCoordinates||C.SceneTransforms.wgs84ToWindowCoordinates;
  const point=p=>{const q=project(viewer.scene,p);if(!q)throw Error('World projection unavailable');return [q.x,q.y];};
  const lengths=[1000,1800,2600].map(depth=>{const a=add(position,direction,depth),b=add(a,right,100),p=point(a),q=point(b);return Math.hypot(p[0]-q[0],p[1]-q[1]);});
  return {viewport:[innerWidth,innerHeight],drawing_buffer:[viewer.scene.drawingBufferWidth,viewer.scene.drawingBufferHeight],
    orthographic:f instanceof C.OrthographicFrustum,width:f.width??null,matrix:Array.from({length:16},(_,i)=>m[i]),
    position:arr(camera.positionWC),direction:arr(camera.directionWC),up:arr(camera.upWC),expected,lengths,
    alignment_errors:anchors.map(a=>{const p=point(a.world);return Math.hypot(p[0]-a.xy[0],p[1]-a.xy[1]);}),
    tiles_loaded:Boolean(viewer.scene.globe.tilesLoaded),cesium_version:C.VERSION};
};
