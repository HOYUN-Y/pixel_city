// Injected only into the ephemeral VWorld page; never persist the API key.
const pilot=window.__landmark={ready:true};
const arr=v=>[v.x,v.y,v.z];
const add=(a,b,s)=>C.Cartesian3.add(a,C.Cartesian3.multiplyByScalar(b,s,new C.Cartesian3()),new C.Cartesian3());
pilot.height=()=>viewer.scene.globe.getHeight(C.Cartographic.fromDegrees(SPEC.lon,SPEC.lat));
pilot.prepare=(height,ortho)=>{
  if(!Number.isFinite(height))throw Error('Target terrain is missing');
  const target=C.Cartesian3.fromDegrees(SPEC.lon,SPEC.lat,height+80);
  viewer.camera.lookAt(target,new C.HeadingPitchRange(C.Math.toRadians(CAMERA.heading_deg),C.Math.toRadians(CAMERA.pitch_deg),CAMERA.range_m));
  const f=ortho?new C.OrthographicFrustum():new C.PerspectiveFrustum();
  f.aspectRatio=1;f.near=1;f.far=10000;
  if(ortho)f.width=800;else f.fov=2*Math.atan(800/(2*CAMERA.range_m));
  viewer.camera.frustum=f;pilot.terrain=height;
  const camera=viewer.camera;
  pilot.expected={position:arr(camera.positionWC),direction:arr(camera.directionWC),up:arr(camera.upWC)};
  pilot.bars=[-250,0,250].map(d=>{
    const p=add(add(target,camera.directionWC,d),camera.upWC,d/2);
    return [add(p,camera.rightWC,-50),add(p,camera.rightWC,50)];
  });
  document.querySelector('#state').style.display='none';viewer.scene.requestRender();
};
pilot.measure=()=>{
  const camera=viewer.camera,f=camera.frustum,m=f.projectionMatrix;
  const project=C.SceneTransforms.worldToWindowCoordinates||C.SceneTransforms.wgs84ToWindowCoordinates;
  const point=p=>{const q=project(viewer.scene,p);if(!q)throw Error('Reference projection failed');return [q.x,q.y];};
  const lines=pilot.bars.map(b=>b.map(point));
  return {viewport:[innerWidth,innerHeight],drawing_buffer:[viewer.scene.drawingBufferWidth,viewer.scene.drawingBufferHeight],
    orthographic:f instanceof C.OrthographicFrustum,width:f.width??null,matrix:Array.from({length:16},(_,i)=>m[i]),
    position:arr(camera.positionWC),direction:arr(camera.directionWC),up:arr(camera.upWC),expected:pilot.expected,
    lines,lengths:lines.map(([a,b])=>Math.hypot(a[0]-b[0],a[1]-b[1])),terrain:pilot.terrain,
    ground_anchor:point(C.Cartesian3.fromDegrees(SPEC.lon,SPEC.lat,pilot.terrain)),
    tiles_loaded:Boolean(viewer.scene.globe.tilesLoaded),cesium_version:C.VERSION};
};
