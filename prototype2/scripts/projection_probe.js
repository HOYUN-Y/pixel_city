// Injected into the existing ephemeral VWorld page. Never contains a persisted key.
const probe=window.__probe={ready:true,mode:null,bars:[],height:null};
probe.heightAtTarget=()=>viewer.scene.globe.getHeight(C.Cartographic.fromDegrees(SPEC.lon,SPEC.lat));
probe.prepare=(mode,height)=>{
  if(!Number.isFinite(height))throw Error('Terrain height unavailable');
  const target=C.Cartesian3.fromDegrees(SPEC.lon,SPEC.lat,height+80);
  viewer.camera.lookAt(target,new C.HeadingPitchRange(C.Math.toRadians(CAMERA.heading_deg),C.Math.toRadians(CAMERA.pitch_deg),CAMERA.range_m));
  const f=mode==='orthographic'?new C.OrthographicFrustum():new C.PerspectiveFrustum();
  f.aspectRatio=1;f.near=1;f.far=10000;
  if(mode==='orthographic')f.width=1600;else f.fov=2*Math.atan(1600/(2*CAMERA.range_m));
  viewer.camera.frustum=f;
  probe.mode=mode;probe.height=height;probe.bars=[];
  const add=(a,b,s)=>C.Cartesian3.add(a,C.Cartesian3.multiplyByScalar(b,s,new C.Cartesian3()),new C.Cartesian3());
  for(const [depth,up] of [[-400,-250],[0,0],[400,250]]){
    const center=add(add(target,viewer.camera.directionWC,depth),viewer.camera.upWC,up);
    probe.bars.push([add(center,viewer.camera.rightWC,-50),add(center,viewer.camera.rightWC,50)]);
  }
  document.querySelector('#state').style.display='none';viewer.scene.requestRender();
};
probe.measure=()=>{
  const camera=viewer.camera,f=camera.frustum,m=f.projectionMatrix;
  const project=C.SceneTransforms.worldToWindowCoordinates||C.SceneTransforms.wgs84ToWindowCoordinates;
  if(!project)throw Error('World-to-window projection unavailable');
  const lines=probe.bars.map(bar=>bar.map(p=>{const v=project(viewer.scene,p);if(!v)throw Error('Reference outside valid projection');return [v.x,v.y];}));
  return {mode:probe.mode,height:probe.height,frustum:f.constructor.name,
    orthographic:f instanceof C.OrthographicFrustum,matrix:Array.from({length:16},(_,i)=>m[i]),
    lines,lengths:lines.map(([a,b])=>Math.hypot(a[0]-b[0],a[1]-b[1])),
    position:[camera.positionWC.x,camera.positionWC.y,camera.positionWC.z],
    direction:[camera.directionWC.x,camera.directionWC.y,camera.directionWC.z],
    up:[camera.upWC.x,camera.upWC.y,camera.upWC.z],
    width:f.width??null,near:f.near,far:f.far,
    tiles_loaded:Boolean(viewer.scene.globe.tilesLoaded),cesium_version:C.VERSION,
    viewport:[innerWidth,innerHeight],drawing_buffer:[viewer.scene.drawingBufferWidth,viewer.scene.drawingBufferHeight]};
};
probe.guides=show=>{
  document.querySelector('#probe-guides')?.remove();if(!show)return;
  const canvas=document.createElement('canvas');canvas.id='probe-guides';canvas.width=canvas.height=1536;
  canvas.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:100';document.body.append(canvas);
  const ctx=canvas.getContext('2d');ctx.font='bold 20px monospace';
  probe.measure().lines.forEach(([a,b],i)=>{ctx.strokeStyle=['#ff5070','#20e0ff','#ffff50'][i];ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();ctx.fillText('100 m / '+Math.hypot(a[0]-b[0],a[1]-b[1]).toFixed(2)+' px',b[0]+12,b[1]);});
};
