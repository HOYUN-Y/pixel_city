export function validateDense(m,o){
  if(m.kind!=='city-dense-pilot'||m.version!==1||m.width!==4608||m.height!==3072||m.tile_size!==512||JSON.stringify(m.levels)!=='[0.25,0.5,1]')throw Error('지원하지 않는 고밀도 지도');
  const xy=p=>Array.isArray(p)&&p.length===2&&p.every((v,i)=>Number.isFinite(v)&&v>=0&&v<=[m.width,m.height][i]);
  const rect=r=>Array.isArray(r)&&r.length===4&&r.every(Number.isInteger)&&r[0]>=0&&r[1]>=0&&r[2]>0&&r[3]>0&&r[0]+r[2]<=m.width&&r[1]+r[3]<=m.height;
  if(!xy(m.initialView?.center)||m.initialView.scale!==.5)throw Error('초기 화면 불일치');
  const ids=new Set(),masks=new Set();
  const spotIds=new Set();
  if(!Array.isArray(o.spots))throw Error('장소 목록 오류');
  for(const s of o.spots){
    if(typeof s.id!=='string'||!s.id||spotIds.has(s.id)||!xy(s.xy))throw Error('장소 ID 또는 위치 오류');
    spotIds.add(s.id);
    if(s.selectionMode!==undefined&&(s.selectionMode!=='location-only'||s.hitPolygon!==undefined))throw Error('위치 안내 선택 설정 오류');
    if(s.hitPolygon!==undefined&&(!Array.isArray(s.hitPolygon)||s.hitPolygon.length<3||s.hitPolygon.some(p=>!xy(p))||Math.abs(s.hitPolygon.reduce((a,p,i)=>{const q=s.hitPolygon[(i+1)%s.hitPolygon.length];return a+p[0]*q[1]-q[0]*p[1];},0))<1))throw Error('장소 선택 윤곽 오류');
  }
  if(!Array.isArray(o.landmarks)||o.landmarks.length!==3)throw Error('세 랜드마크 필요');
  for(const l of o.landmarks){if(ids.has(l.id)||masks.has(l.occluder_id)||!rect(l.rect)||!xy(l.anchor)||!o.spots.some(s=>s.id===l.id&&xy(s.xy)))throw Error('랜드마크 배치 오류');ids.add(l.id);masks.add(l.occluder_id);}
  if([...ids].sort().join()!=='bosingak,gwanghwamun,jongno-tower')throw Error('랜드마크 범위 변경');
  if(o.reveal?.targetId!=='bosingak'||!rect(o.reveal.rect)||!o.landmarks.find(l=>l.id==='bosingak').reveal_only)throw Error('보신각 재구성 영역 오류');
  if(!Array.isArray(o.route?.points)||o.route.points.length<2||o.route.points.some(p=>!xy(p.xy)||(p.behind||[]).some(id=>!masks.has(id))))throw Error('보행 경로 오류');
  if(!xy(o.traffic?.focus)||!Number.isFinite(o.traffic.speed)||o.traffic.speed<=0||![2,4].includes(o.traffic.lanes.length))throw Error('차량 설정 오류');
  for(const l of o.traffic.lanes)if(!xy(l.start)||!xy(l.end)||!Array.isArray(l.offsets)||l.offsets.some(n=>!Number.isFinite(n)||n<0||n>=1))throw Error('차량 경로 오류');
  if(o.traffic.lanes.length===4&&(o.traffic.lanes.some(l=>typeof l.id!=='string'||!l.id||l.offsets.length!==1)||new Set(o.traffic.lanes.map(l=>l.id)).size!==4))throw Error('차량 ID 중복');
  for(const l of o.traffic.lanes)if(l.points!==undefined&&(!Array.isArray(l.points)||l.points.length<2||l.points.some(p=>!xy(p))||!l.points.slice(1).some((p,i)=>p[0]!==l.points[i][0]||p[1]!==l.points[i][1])))throw Error('차량 꺾은선 오류');
  if(o.reveal.foregroundMask&&(!/^[a-zA-Z0-9_-]+\.png$/.test(o.reveal.foregroundMask)||!m.asset_sha256?.[o.reveal.foregroundMask]))throw Error('전경 마스크 오류');
  if(o.reveal.auto!==undefined&&(typeof o.reveal.auto!=='boolean'||(o.reveal.auto&&!o.reveal.foregroundMask)))throw Error('자동 가림 설정 오류');
  if(o.traffic.focuses&&(!Array.isArray(o.traffic.focuses)||o.traffic.focuses.some(f=>typeof f.id!=='string'||typeof f.label!=='string'||!xy(f.xy))))throw Error('차량 구간 오류');
  const occluders=o.traffic.occluders??[],seen=new Set();
  if(!Array.isArray(occluders)||occluders.length>32)throw Error('차량 가림 목록 오류');
  for(const item of occluders){
    if(typeof item.id!=='string'||!item.id||seen.has(item.id)||!rect(item.rect)||typeof item.mask!=='string'||
      !/^[a-zA-Z0-9_-]+\.png$/.test(item.mask)||!m.asset_sha256?.[item.mask]||
      !Array.isArray(item.lanes)||!item.lanes.length||item.lanes.some(id=>!o.traffic.lanes.some(l=>l.id===id)))throw Error('차량 가림 영역 오류');
    seen.add(item.id);
  }
  return o;
}
export function cropHit(p,rect,pixels){const x=Math.floor(p.x-rect[0]),y=Math.floor(p.y-rect[1]);return x>=0&&y>=0&&x<rect[2]&&y<rect[3]&&pixels[(y*rect[2]+x)*4]>=128;}

export function intersectRect(a,b){const x=Math.max(a[0],b[0]),y=Math.max(a[1],b[1]),r=Math.min(a[0]+a[2],b[0]+b[2]),d=Math.min(a[1]+a[3],b[1]+b[3]);return r>x&&d>y?[x,y,r-x,d-y]:null;}

// Draw into a vehicle-sized offscreen canvas, not the map canvas. Thus masking
// can never erase background pixels, landmarks, or a different vehicle.
export function paintVehicle(ctx,image,rect,occluders){
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
  ctx.clearRect(0,0,rect[2],rect[3]);ctx.imageSmoothingEnabled=false;
  ctx.drawImage(image,0,0,rect[2],rect[3]);ctx.globalCompositeOperation='destination-out';
  let applied=0;
  for(const o of occluders){const hit=intersectRect(rect,o.rect);if(!hit)continue;const [x,y,w,h]=hit;
    ctx.globalAlpha=o.opacity??1;
    ctx.drawImage(o.shape,x-o.rect[0],y-o.rect[1],w,h,x-rect[0],y-rect[1],w,h);applied++;
  }
  ctx.restore();return applied;
}
