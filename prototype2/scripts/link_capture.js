// One immutable parent camera, translated left 300m; no per-tile camera fitting.
const link=window.__link={ready:true};
const vec=a=>new C.Cartesian3(...a),arr=v=>[v.x,v.y,v.z];
const add=(a,b,s)=>C.Cartesian3.add(a,C.Cartesian3.multiplyByScalar(b,s,new C.Cartesian3()),new C.Cartesian3());
const direction=vec(BASE.direction),up=vec(BASE.up),right=C.Cartesian3.cross(direction,up,new C.Cartesian3());
const origin=vec(BASE.position),position=add(origin,right,-300);
const expected={position:arr(position),direction:BASE.direction,up:BASE.up};
const anchors=[];
for(const depth of [500,900,1600])for(const [x,y] of [[100,100],[512,600],[900,900]])anchors.push({world:add(add(add(origin,direction,depth),right,(x-512)/1.28),up,(512-y)/1.28),xy:[x+768,y]});
link.prepare=()=>{
  viewer.camera.lookAtTransform(C.Matrix4.IDENTITY);
  viewer.camera.setView({destination:position,orientation:{direction,up},endTransform:C.Matrix4.IDENTITY});
  const f=new C.OrthographicFrustum();f.aspectRatio=1792/1024;f.width=1400;f.near=1;f.far=10000;viewer.camera.frustum=f;
  document.querySelector('#state').style.display='none';viewer.scene.requestRender();
};
link.warm=async xy=>{
  link.prepare();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
  const target=viewer.scene.globe.pick(viewer.camera.getPickRay(new C.Cartesian2(...xy)),viewer.scene);
  if(!target)throw Error('Missing source ground');
  viewer.camera.lookAt(target,new C.HeadingPitchRange(C.Math.toRadians(22.5),C.Math.toRadians(-30),900));
  const f=new C.PerspectiveFrustum();f.aspectRatio=1792/1024;f.fov=Math.PI/3;f.near=1;f.far=10000;viewer.camera.frustum=f;viewer.scene.requestRender();
};
link.measure=()=>{
  const camera=viewer.camera,f=camera.frustum,m=f.projectionMatrix;
  const project=C.SceneTransforms.worldToWindowCoordinates||C.SceneTransforms.wgs84ToWindowCoordinates;
  const point=p=>{const q=project(viewer.scene,p);if(!q)throw Error('Projection unavailable');return[q.x,q.y];};
  const lengths=[500,900,1600].map(depth=>{const a=add(position,direction,depth),b=add(a,right,100),p=point(a),q=point(b);return Math.hypot(p[0]-q[0],p[1]-q[1]);});
  const lon=C.Math.toRadians(SPEC.lon),east=new C.Cartesian3(-Math.sin(lon),Math.cos(lon),0);
  const eastScreen=[C.Cartesian3.dot(east,right),-C.Cartesian3.dot(east,up)];
  return {viewport:[innerWidth,innerHeight],drawing_buffer:[viewer.scene.drawingBufferWidth,viewer.scene.drawingBufferHeight],orthographic:f instanceof C.OrthographicFrustum,width:f.width??null,
    matrix:Array.from({length:16},(_,i)=>m[i]),position:arr(camera.positionWC),direction:arr(camera.directionWC),up:arr(camera.upWC),expected,lengths,east_screen:eastScreen,
    alignment_errors:anchors.map(a=>{const p=point(a.world);return Math.hypot(p[0]-a.xy[0],p[1]-a.xy[1]);}),tiles_loaded:Boolean(viewer.scene.globe.tilesLoaded),cesium_version:C.VERSION};
};
