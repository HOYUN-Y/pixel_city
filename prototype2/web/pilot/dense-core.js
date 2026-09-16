export function validateDense(m,o){
  if(m.kind!=='city-dense-pilot'||m.version!==1||m.width!==4608||m.height!==3072||m.tile_size!==512||JSON.stringify(m.levels)!=='[0.25,0.5,1]')throw Error('지원하지 않는 고밀도 지도');
  const xy=p=>Array.isArray(p)&&p.length===2&&p.every((v,i)=>Number.isFinite(v)&&v>=0&&v<=[m.width,m.height][i]);
  const rect=r=>Array.isArray(r)&&r.length===4&&r.every(Number.isInteger)&&r[0]>=0&&r[1]>=0&&r[2]>0&&r[3]>0&&r[0]+r[2]<=m.width&&r[1]+r[3]<=m.height;
  if(!xy(m.initialView?.center)||m.initialView.scale!==.5)throw Error('초기 화면 불일치');
  const ids=new Set(),masks=new Set();
  if(!Array.isArray(o.landmarks)||o.landmarks.length!==3)throw Error('세 랜드마크 필요');
  for(const l of o.landmarks){if(ids.has(l.id)||masks.has(l.occluder_id)||!rect(l.rect)||!xy(l.anchor)||!o.spots.some(s=>s.id===l.id&&xy(s.xy)))throw Error('랜드마크 배치 오류');ids.add(l.id);masks.add(l.occluder_id);}
  if([...ids].sort().join()!=='bosingak,gwanghwamun,jongno-tower')throw Error('랜드마크 범위 변경');
  if(o.reveal?.targetId!=='bosingak'||!rect(o.reveal.rect)||!o.landmarks.find(l=>l.id==='bosingak').reveal_only)throw Error('보신각 재구성 영역 오류');
  if(!Array.isArray(o.route?.points)||o.route.points.length<2||o.route.points.some(p=>!xy(p.xy)||(p.behind||[]).some(id=>!masks.has(id))))throw Error('보행 경로 오류');
  if(!xy(o.traffic?.focus)||!Number.isFinite(o.traffic.speed)||o.traffic.speed<=0||o.traffic.lanes.length!==2)throw Error('차량 설정 오류');
  for(const l of o.traffic.lanes)if(!xy(l.start)||!xy(l.end)||!Array.isArray(l.offsets)||l.offsets.some(n=>!Number.isFinite(n)||n<0||n>=1))throw Error('차량 경로 오류');
  return o;
}
export function cropHit(p,rect,pixels){const x=Math.floor(p.x-rect[0]),y=Math.floor(p.y-rect[1]);return x>=0&&y>=0&&x<rect[2]&&y<rect[3]&&pixels[(y*rect[2]+x)*4]>=128;}
